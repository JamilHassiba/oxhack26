import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.orchestrator import store
from app.routers import voice_tools

URL = "/webhooks/elevenlabs/tools/request_payment_approval"
CALL = "11111111-1111-1111-1111-111111111111"
PAYMENT = {"id": "pay-1", "amount": 2000, "currency": "GBP", "status": "pending_approval"}


@pytest.fixture
def world(monkeypatch):
    w = {"outcome": "created", "statuses": ["pending_approval"], "requests": [], "secret": ""}

    async def request_payment(call_id, amount, currency, description):
        if call_id != CALL:
            raise store.CallNotFound(call_id)
        w["requests"].append((call_id, amount, currency, description))
        return {"outcome": w["outcome"], "payment": PAYMENT if w["outcome"] in ("created", "existing") else None}

    async def payment_status(payment_id):
        return w["statuses"].pop(0) if len(w["statuses"]) > 1 else w["statuses"][0]

    async def find_call_by_conversation(conversation_id):
        return CALL if conversation_id == "conv-1" else None

    monkeypatch.setattr(store, "request_payment", request_payment)
    monkeypatch.setattr(store, "payment_status", payment_status)
    monkeypatch.setattr(store, "find_call_by_conversation", find_call_by_conversation)
    monkeypatch.setattr(voice_tools, "POLL_SECONDS", 0)
    return w


def client(world, wait=0.0, secret=""):
    app = create_app(Settings(_env_file=None, payment_wait_seconds=wait, elevenlabs_tool_secret=secret))
    return TestClient(app)


def test_creates_request_and_reports_approval(world):
    world["statuses"] = ["pending_approval", "pending_approval", "paid"]  # user clicks Approve while we wait

    with client(world, wait=5) as c:
        body = c.post(URL, json={"call_id": CALL, "amount": "20", "description": "Deposit for 4"}).json()

    assert world["requests"] == [(CALL, 2000, "GBP", "Deposit for 4")]  # pounds -> pence
    assert body["status"] == "approved" and body["payment_id"] == "pay-1"
    assert "£20.00" in body["message"]


def test_denied(world):
    world["statuses"] = ["denied"]
    with client(world) as c:
        body = c.post(URL, json={"call_id": CALL, "amount": 20}).json()
    assert body["status"] == "denied" and "Don't agree" in body["message"]


def test_no_answer_in_time_is_pending(world):
    with client(world, wait=0) as c:
        body = c.post(URL, json={"call_id": CALL, "amount": 20.5}).json()
    assert body["status"] == "pending" and body["payment_id"] == "pay-1"
    assert world["requests"][0][1] == 2050


def test_conversation_id_fallback(world):
    with client(world) as c:
        assert c.post(URL, json={"conversation_id": "conv-1", "amount": 20}).json()["status"] == "pending"
        assert c.post(URL, json={"conversation_id": "nope", "amount": 20}).status_code == 404


def test_no_payments_permission(world):
    world["outcome"] = "not_allowed"
    with client(world) as c:
        body = c.post(URL, json={"call_id": CALL, "amount": 20}).json()
    assert body["status"] == "not_allowed" and body["payment_id"] is None


@pytest.mark.parametrize("amount", ["0", "-5", "twenty", "9999"])
def test_bad_amounts_are_not_requested(world, amount):
    with client(world) as c:
        body = c.post(URL, json={"call_id": CALL, "amount": amount}).json()
    assert body["status"] == "invalid"
    assert world["requests"] == []


def test_unknown_call(world):
    with client(world) as c:
        assert c.post(URL, json={"call_id": "22222222-2222-2222-2222-222222222222", "amount": 20}).status_code == 404


def test_secret_required_when_set(world):
    with client(world, secret="s3cret") as c:
        assert c.post(URL, json={"call_id": CALL, "amount": 20}).status_code == 401
        ok = c.post(URL, json={"call_id": CALL, "amount": 20}, headers={"X-Tool-Secret": "s3cret"})
        assert ok.status_code == 200


def test_pounds_to_pence():
    assert voice_tools.pounds_to_pence("£20") == 2000
    assert voice_tools.pounds_to_pence("12.345") == 1234  # rounds half to even, never fractional pence
    assert voice_tools.pounds_to_pence("1,000") is None  # over the £500 cap
