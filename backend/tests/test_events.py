import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.routers import events

CALL = "11111111-1111-1111-1111-111111111111"
T0 = datetime(2026, 10, 25, 17, 2, 1, 481000, tzinfo=timezone.utc)


def row(seconds, kind, **payload):
    return {"ts": T0 + timedelta(seconds=seconds), "call_id": CALL, "kind": kind, "payload": {"text": kind, **payload}}


ROWS = [
    row(0, "dialing", to_number="+44"),
    row(5, "answered"),
    row(6, "transcript_line", speaker="Maya", text="Hi, a table for 4 please."),
    row(9, "ended", reason="completed", duration_seconds=8),
    row(20, "transcript_line", speaker="Maya", text="never sent: after ended"),
]


@pytest.fixture
def client(monkeypatch):
    seen = {"after": []}

    async def call_exists(call_id):
        return call_id == CALL

    async def events_after(call_id, after):
        seen["after"].append(after)
        return [r for r in ROWS if after is None or r["ts"] > after]

    async def ended_by(call_id, at):
        return at >= ROWS[3]["ts"]

    monkeypatch.setattr(events, "call_exists", call_exists)
    monkeypatch.setattr(events, "events_after", events_after)
    monkeypatch.setattr(events, "ended_by", ended_by)
    with TestClient(create_app(Settings(_env_file=None))) as c:
        c.seen = seen
        yield c


def frames(body):
    """Parse an SSE body into [{event, id, data}] (ignoring comment/ping lines)."""
    out = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "data" in fields:
            out.append(fields)
    return out


def test_streams_events_in_order_and_closes_after_ended(client):
    response = client.get(f"/calls/{CALL}/events/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    got = frames(response.text)
    assert [f["event"] for f in got] == ["dialing", "answered", "transcript_line", "ended"]
    first = json.loads(got[0]["data"])
    assert first == {
        "ts": "2026-10-25T17:02:01.481000Z",  # same format as task.events from GET /tasks/{id}
        "call_id": CALL,
        "kind": "dialing",
        # Evan's CallEvent keeps only what the UI reads (speaker, text) and, like task.events, omits empty
        # fields: an extra "speaker": null made the UI show every event twice.
        "payload": {"text": "dialing"},
    }
    assert json.loads(got[2]["data"])["payload"]["speaker"] == "Maya"
    assert got[0]["id"] == ROWS[0]["ts"].isoformat()


def test_resumes_after_last_event_id(client):
    response = client.get(f"/calls/{CALL}/events/stream", headers={"Last-Event-ID": ROWS[1]["ts"].isoformat()})

    assert [f["event"] for f in frames(response.text)] == ["transcript_line", "ended"]
    assert client.seen["after"][0] == ROWS[1]["ts"]


def test_reconnect_after_ended_gets_204_so_the_browser_stops(client):
    response = client.get(f"/calls/{CALL}/events/stream", headers={"Last-Event-ID": ROWS[3]["ts"].isoformat()})
    assert response.status_code == 204


@pytest.mark.parametrize("call_id", ["22222222-2222-2222-2222-222222222222", "not-a-uuid"])
def test_unknown_call_is_404(client, call_id):
    assert client.get(f"/calls/{call_id}/events/stream").status_code == 404
