import asyncio
from types import SimpleNamespace

import pytest
import stripe
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.orchestrator import store
from app.routers import payments as router
from app.tools import payments

PAYMENT = {
    "id": "pay-1",
    "task_id": "task-1",
    "amount": 2000,
    "currency": "GBP",
    "merchant": "The Ivy Oxford",
    "description": "",
    "status": "approved",
    "stripe_pi_id": None,
}


@pytest.fixture
def api(monkeypatch):
    state = {"decided": [], "charged": [], "charge_error": None}

    async def decide_payment(payment_id, approve):
        if payment_id == "missing":
            raise store.PaymentNotFound(payment_id)
        if payment_id == "done":
            raise store.PaymentAlreadyDecided("paid")
        state["decided"].append((payment_id, approve))
        return {**PAYMENT, "status": "approved" if approve else "denied"}

    async def mark_paid(payment_id, stripe_pi_id):
        return {**PAYMENT, "status": "paid", "stripe_pi_id": stripe_pi_id}

    async def fake_charge(payment):
        if state["charge_error"]:
            raise payments.ChargeFailed(state["charge_error"])
        state["charged"].append(payment["id"])
        return "pi_123"

    monkeypatch.setattr(store, "decide_payment", decide_payment)
    monkeypatch.setattr(store, "mark_paid", mark_paid)
    monkeypatch.setattr(router, "charge", fake_charge)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        client.state = state
        yield client


def test_approve_charges_and_returns_paid_payment(api):
    response = api.post("/payments/pay-1/approve")

    assert response.status_code == 200
    assert response.json() == {
        "id": "pay-1", "task_id": "task-1", "amount": 2000, "currency": "GBP",
        "merchant": "The Ivy Oxford", "status": "paid",
    }  # same shape as the frontend's Payment type; Stripe ids stay internal
    assert api.state["decided"] == [("pay-1", True)] and api.state["charged"] == ["pay-1"]


def test_deny_does_not_charge(api):
    response = api.post("/payments/pay-1/deny")

    assert response.json()["status"] == "denied"
    assert api.state["charged"] == []


def test_failed_charge_is_readable_and_retryable(api):
    api.state["charge_error"] = "Your card was declined."

    response = api.post("/payments/pay-1/approve")

    assert response.status_code == 502
    assert "Your card was declined." in response.json()["detail"]


@pytest.mark.parametrize(("payment_id", "code"), [("missing", 404), ("done", 409)])
def test_unknown_or_already_decided(api, payment_id, code):
    for action in ("approve", "deny"):
        response = api.post(f"/payments/{payment_id}/{action}")
        assert response.status_code == code and isinstance(response.json()["detail"], str)
    assert api.state["charged"] == []


def use_key(monkeypatch, key):
    monkeypatch.setattr(payments, "get_settings", lambda: Settings(_env_file=None, stripe_secret_key=key))


def test_no_key_uses_stand_in(monkeypatch):
    use_key(monkeypatch, "")
    assert asyncio.run(payments.charge(PAYMENT)) == "simulated_pay-1"


def test_live_key_is_refused(monkeypatch):
    use_key(monkeypatch, "sk_live_abc")
    with pytest.raises(payments.ChargeFailed, match="test keys"):
        asyncio.run(payments.charge(PAYMENT))


def fake_stripe(monkeypatch, result=None, error=None):
    calls = []

    async def create_async(params, options):
        calls.append((params, options))
        if error:
            raise error
        return result

    client = SimpleNamespace(v1=SimpleNamespace(payment_intents=SimpleNamespace(create_async=create_async)))
    monkeypatch.setattr(payments.stripe, "StripeClient", lambda key, http_client: client)
    return calls


def test_test_key_charges_test_card_once(monkeypatch):
    use_key(monkeypatch, "sk_test_abc")
    calls = fake_stripe(monkeypatch, result=SimpleNamespace(id="pi_9", status="succeeded"))

    assert asyncio.run(payments.charge(PAYMENT)) == "pi_9"
    params, options = calls[0]
    assert (params["amount"], params["currency"], params["payment_method"]) == (2000, "gbp", "pm_card_visa")
    assert options == {"idempotency_key": "payment-pay-1"}


def test_stripe_error_becomes_charge_failed(monkeypatch):
    use_key(monkeypatch, "sk_test_abc")
    fake_stripe(monkeypatch, error=stripe.CardError("declined", None, "card_declined"))

    with pytest.raises(payments.ChargeFailed):
        asyncio.run(payments.charge(PAYMENT))
