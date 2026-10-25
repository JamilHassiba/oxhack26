import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import hang_up

REAL = Settings(_env_file=None, elevenlabs_api_key="xi", twilio_account_sid="AC1", twilio_auth_token="tok")


@pytest.fixture
def fake(monkeypatch):
    """Fake database, Twilio and background work, recording what hang_up did."""
    w = {"ended": False, "settings": REAL, "log": [], "twilio_error": None, "background": []}

    async def call_ended(call_id):
        return None if call_id == "missing" else w["ended"]

    async def save_outcome(call_id):
        w["log"].append(("outcome saved", call_id))

    async def clear_outcome(call_id):
        w["log"].append(("outcome cleared", call_id))

    async def end_twilio_call(settings, call_sid):
        if w["twilio_error"]:
            raise w["twilio_error"]
        w["log"].append(("twilio hung up", call_sid))

    def in_background(coro):
        w["background"].append(coro.__qualname__)
        coro.close()  # not run: these wait for the webhook / write to the database

    monkeypatch.setattr(hang_up, "get_settings", lambda: w["settings"])
    monkeypatch.setattr(hang_up, "call_ended", call_ended)
    monkeypatch.setattr(hang_up, "_save_outcome", save_outcome)
    monkeypatch.setattr(hang_up, "_clear_outcome", clear_outcome)
    monkeypatch.setattr(hang_up, "_end_twilio_call", end_twilio_call)
    monkeypatch.setattr(hang_up, "_in_background", in_background)
    monkeypatch.setattr(hang_up, "_call_sids", {})
    return w


def test_real_call_saves_outcome_then_asks_twilio_to_hang_up(fake):
    hang_up.remember("call-1", "CA123")

    asyncio.run(hang_up.hang_up("call-1"))

    # Outcome first, so the post-call webhook's on_call_finished sees "you hung up" and doesn't call back.
    assert fake["log"] == [("outcome saved", "call-1"), ("twilio hung up", "CA123")]
    assert fake["background"] == ["_end_if_no_webhook"]


def test_twilio_failure_undoes_the_outcome(fake):
    hang_up.remember("call-1", "CA123")
    fake["twilio_error"] = RuntimeError("Twilio down")

    with pytest.raises(hang_up.HangUpFailed):
        asyncio.run(hang_up.hang_up("call-1"))

    assert fake["log"] == [("outcome saved", "call-1"), ("outcome cleared", "call-1")]
    assert fake["background"] == []


def test_practice_call_ends_straight_away(fake):
    fake["settings"] = Settings(_env_file=None)

    asyncio.run(hang_up.hang_up("call-1"))

    assert fake["log"] == [("outcome saved", "call-1")]
    assert fake["background"] == ["end_ourselves"]


@pytest.mark.parametrize(
    "settings, call_sid",
    [
        (Settings(_env_file=None, elevenlabs_api_key="xi"), "CA123"),  # no Twilio keys
        (REAL, None),  # ElevenLabs gave no callSid (or the server restarted mid-call)
    ],
)
def test_unavailable_without_twilio_keys_or_call_sid(fake, settings, call_sid):
    fake["settings"] = settings
    hang_up.remember("call-1", call_sid)

    with pytest.raises(hang_up.HangUpUnavailable):
        asyncio.run(hang_up.hang_up("call-1"))
    assert fake["log"] == []


def test_hung_up_outcome_is_not_retried():
    from app.orchestrator.callbacks import RETRYABLE
    from app.orchestrator.outcome import OUTCOME_SCHEMA

    assert set(hang_up.HUNG_UP_OUTCOME) == set(OUTCOME_SCHEMA["required"])
    assert hang_up.HUNG_UP_OUTCOME["result"] not in RETRYABLE


def test_start_call_is_still_importable_by_the_phone_tool():
    # hang_up must not import the orchestrator at load time, or this circular import turns real calls into
    # practice runs (phone.py falls back to the stand-in on ImportError).
    from app.tools import phone

    assert phone.start_call is not None


@pytest.mark.parametrize(
    "call_id, ended, code",
    [("call-1", False, 202), ("missing", False, 404), ("call-1", True, 409)],
)
def test_endpoint_status_codes(fake, call_id, ended, code):
    fake["ended"] = ended
    hang_up.remember("call-1", "CA123")
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.post(f"/calls/{call_id}/hang-up").status_code == code


def test_endpoint_explains_when_hang_up_is_not_set_up(fake):
    fake["settings"] = Settings(_env_file=None, elevenlabs_api_key="xi")
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/calls/call-1/hang-up")
    assert response.status_code == 503 and "TWILIO_ACCOUNT_SID" in response.json()["detail"]
