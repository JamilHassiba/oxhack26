import asyncio

import pytest

from app.config import Settings
from app.services import call_status


@pytest.fixture
def twilio(monkeypatch):
    """Fake Twilio + database: each poll returns the next status; emitted events are recorded."""
    w = {"statuses": [], "events": [], "ended": False}

    async def fetch_status(client, call_sid):
        return w["statuses"].pop(0) if len(w["statuses"]) > 1 else w["statuses"][0]

    async def call_ended(call_id):
        return w["ended"]

    async def emit(call_id, kind, payload, conn=None):
        w["events"].append(kind)

    monkeypatch.setattr(call_status, "fetch_status", fetch_status)
    monkeypatch.setattr(call_status, "call_ended", call_ended)
    monkeypatch.setattr(call_status.events, "emit", emit)
    monkeypatch.setattr(call_status, "POLL_SECONDS", 0)
    return w


def test_ringing_then_answered(twilio):
    twilio["statuses"] = ["queued", "ringing", "ringing", "in-progress"]
    asyncio.run(call_status.follow("call-1", "CA1"))
    assert twilio["events"] == ["ringing", "answered"]


def test_not_answered_writes_no_answered(twilio):
    twilio["statuses"] = ["ringing", "no-answer"]
    asyncio.run(call_status.follow("call-1", "CA1"))
    assert twilio["events"] == ["ringing"]


def test_stops_once_the_call_has_ended(twilio):
    twilio["statuses"] = ["ringing"]
    twilio["ended"] = True
    asyncio.run(call_status.follow("call-1", "CA1"))
    assert twilio["events"] == []


def test_does_nothing_without_twilio_credentials(monkeypatch):
    monkeypatch.setattr(call_status, "get_settings", lambda: Settings(_env_file=None, twilio_account_sid=""))
    call_status.start("call-1", "CA1")  # would need a running event loop if it tried to follow
    assert not call_status._followers
