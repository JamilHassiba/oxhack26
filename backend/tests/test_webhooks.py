import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.routers import webhooks

SECRET = "wsec_test"
START = 1_761_400_000  # unix seconds

TRANSCRIPTION = {
    "type": "post_call_transcription",
    "data": {
        "conversation_id": "conv_1",
        "transcript": [
            {"role": "agent", "message": "[calm] Hi, I'm Maya, calling on behalf of Jamil.", "time_in_call_secs": 0},
            {"role": "user", "message": "Sure, six works.", "time_in_call_secs": 4},
            {"role": "agent", "message": None, "time_in_call_secs": 5},  # tool call turn: no text
            {"role": "agent", "message": "[happy] Thanks, goodbye.", "time_in_call_secs": 6},
        ],
        "metadata": {"start_time_unix_secs": START, "call_duration_secs": 9},
        "analysis": {"transcript_summary": "Booked a table for 4 at 6pm."},
        "conversation_initiation_client_data": {"dynamic_variables": {"call_id": "call-1", "agent_name": "Maya"}},
    },
}


def sign(body: bytes, timestamp: int | None = None, secret: str = SECRET) -> str:
    t = str(timestamp or int(time.time()))
    return f"t={t},v0=" + hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()


def test_signature_accepts_a_valid_one():
    body = b'{"a": 1}'
    webhooks.verify_signature(body, sign(body), SECRET)


@pytest.mark.parametrize(
    "header",
    [None, "garbage", sign(b"other body"), sign(b'{"a": 1}', secret="wrong"), sign(b'{"a": 1}', timestamp=1000)],
)
def test_signature_rejects_bad_ones(header):
    with pytest.raises(webhooks.InvalidSignature):
        webhooks.verify_signature(b'{"a": 1}', header, SECRET)


def test_parse_transcription_strips_tags_and_empty_turns():
    end = webhooks.parse_webhook(TRANSCRIPTION)
    assert end.call_id == "call-1" and end.conversation_id == "conv_1"
    assert end.reason == "completed" and end.duration_seconds == 9
    assert [(l.role, l.text) for l in end.lines] == [
        ("agent", "Hi, I'm Maya, calling on behalf of Jamil."),
        ("user", "Sure, six works."),
        ("agent", "Thanks, goodbye."),
    ]
    assert end.summary == "Booked a table for 4 at 6pm."


@pytest.mark.parametrize("failure, reason", [("no-answer", "no_answer"), ("busy", "busy"), ("unknown", "failed")])
def test_parse_initiation_failure(failure, reason):
    end = webhooks.parse_webhook(
        {"type": "call_initiation_failure", "data": {"failure_reason": failure, "conversation_id": "c"}}
    )
    assert end.reason == reason and end.lines == []


def test_other_webhook_types_are_ignored():
    assert webhooks.parse_webhook({"type": "post_call_audio", "data": {}}) is None


def test_event_rows_are_in_call_order_and_after_dialing():
    end = webhooks.parse_webhook(TRANSCRIPTION)
    dialing = datetime.fromtimestamp(START, timezone.utc) + timedelta(seconds=1)  # dialing logged just after start
    rows = webhooks.event_rows(end, dialing, agent="Maya", contact="The Ivy Oxford")
    assert [kind for _, kind, _ in rows] == ["answered", "transcript_line", "transcript_line", "transcript_line", "ended"]
    times = [ts for ts, _, _ in rows]
    assert times[0] > dialing and times == sorted(times) and len(set(times)) == len(times)
    assert rows[2][2] == {"speaker": "The Ivy Oxford", "text": "Sure, six works."}
    assert rows[-1][2] == {"text": "Call finished", "reason": "completed", "duration_seconds": 9}


def test_failed_call_has_only_an_ended_event():
    end = webhooks.parse_webhook({"type": "call_initiation_failure", "data": {"failure_reason": "no-answer"}})
    rows = webhooks.event_rows(end, datetime.now(timezone.utc), agent="Maya", contact="Ivy")
    assert [(kind, payload["reason"]) for _, kind, payload in rows] == [("ended", "no_answer")]


@pytest.fixture
def client(monkeypatch):
    seen = {"saved": [], "finished": []}

    async def save_call_end(end):
        seen["saved"].append(end)
        return "call-1"

    async def finish(call_id):
        seen["finished"].append(call_id)

    monkeypatch.setattr(webhooks, "save_call_end", save_call_end)
    monkeypatch.setattr(webhooks, "finish", finish)
    monkeypatch.setattr(webhooks, "get_settings", lambda: Settings(elevenlabs_webhook_secret=SECRET))
    with TestClient(create_app(Settings(database_url=""))) as c:
        yield c, seen


def post(c, payload, header=None):
    body = json.dumps(payload).encode()
    return c.post("/webhooks/elevenlabs/post-call", content=body, headers={"elevenlabs-signature": header or sign(body)})


def test_endpoint_saves_and_finishes_the_call(client):
    c, seen = client
    response = post(c, TRANSCRIPTION)
    assert response.status_code == 200 and response.json() == {"status": "ok", "call_id": "call-1"}
    assert seen["saved"][0].call_id == "call-1" and seen["finished"] == ["call-1"]


def test_endpoint_rejects_bad_signature(client):
    c, seen = client
    assert post(c, TRANSCRIPTION, header="t=1,v0=nope").status_code == 401
    assert seen["saved"] == []


def test_endpoint_ignores_audio_webhooks(client):
    c, seen = client
    assert post(c, {"type": "post_call_audio", "data": {}}).json() == {"status": "ignored"}
    assert seen["saved"] == []


def test_endpoint_needs_a_secret(monkeypatch):
    monkeypatch.setattr(webhooks, "get_settings", lambda: Settings(elevenlabs_webhook_secret=""))
    with TestClient(create_app(Settings(database_url=""))) as c:
        assert post(c, TRANSCRIPTION).status_code == 503
