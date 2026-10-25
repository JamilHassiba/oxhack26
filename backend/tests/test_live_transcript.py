import asyncio
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.routers import webhooks
from app.services import live_transcript
from app.services.transcript import Line, transcript_lines


def turn(role, message, secs):
    return {"role": role, "message": message, "time_in_call_secs": secs}


TURNS = [
    turn("user", "Good evening, The Ivy Oxford.", 1),
    turn("agent", "[warmly] Hi, I'm Maya, an AI assistant calling for Alex.", 3),
    turn("user", "", 5),  # silence: not a line
    turn("user", "How can I help?", 7),
]


def test_transcript_lines_drop_empty_turns_and_emotion_tags():
    assert [(line.role, line.text) for line in transcript_lines(TURNS)] == [
        ("user", "Good evening, The Ivy Oxford."),
        ("agent", "Hi, I'm Maya, an AI assistant calling for Alex."),
        ("user", "How can I help?"),
    ]


@pytest.fixture
def follower(monkeypatch):
    """Fake ElevenLabs + database: each poll returns the next conversation snapshot."""
    w = {"snapshots": [], "written": [], "ended": False, "conversation_id": "conv-1", "errors": 0}

    async def call_state(call_id):
        return w["conversation_id"], w["ended"]

    async def fetch_conversation(client, conversation_id):
        if w["errors"]:
            w["errors"] -= 1
            raise RuntimeError("ElevenLabs hiccup")
        return w["snapshots"].pop(0) if len(w["snapshots"]) > 1 else w["snapshots"][0]

    async def write_new_lines(call_id, lines):
        if w["ended"]:
            return False
        w["written"].extend(lines[len(w["written"]) :])  # like the real one: only lines not stored yet
        return True

    monkeypatch.setattr(live_transcript, "call_state", call_state)
    monkeypatch.setattr(live_transcript, "fetch_conversation", fetch_conversation)
    monkeypatch.setattr(live_transcript, "write_new_lines", write_new_lines)
    monkeypatch.setattr(live_transcript, "POLL_SECONDS", 0)
    return w


def test_writes_lines_as_the_conversation_grows_then_stops_when_done(follower):
    follower["snapshots"] = [
        {"status": "in-progress", "transcript": TURNS[:1]},
        {"status": "in-progress", "transcript": TURNS[:2]},
        {"status": "in-progress", "transcript": TURNS[:2]},  # nothing new this time
        {"status": "done", "transcript": TURNS},
    ]

    asyncio.run(live_transcript.follow("call-1"))

    assert [line.text for line in follower["written"]] == [
        "Good evening, The Ivy Oxford.",
        "Hi, I'm Maya, an AI assistant calling for Alex.",
        "How can I help?",
    ]


def test_never_writes_a_line_that_is_still_being_spoken(follower):
    follower["snapshots"] = [
        {"status": "in-progress", "transcript": [TURNS[0], turn("agent", "Hi, I'm Ma", 3)]},  # mid-sentence
        {"status": "in-progress", "transcript": TURNS[:2] + [turn("user", "How can", 7)]},
        {"status": "done", "transcript": TURNS},
    ]

    asyncio.run(live_transcript.follow("call-1"))

    assert [line.text for line in follower["written"]] == [
        "Good evening, The Ivy Oxford.",
        "Hi, I'm Maya, an AI assistant calling for Alex.",
        "How can I help?",
    ]


def test_stops_once_the_webhook_has_ended_the_call(follower):
    follower["snapshots"] = [{"status": "in-progress", "transcript": TURNS}]
    follower["ended"] = True

    asyncio.run(live_transcript.follow("call-1"))

    assert follower["written"] == []


def test_keeps_going_after_a_temporary_error(follower):
    follower["errors"] = 2
    follower["snapshots"] = [{"status": "done", "transcript": TURNS[:1]}]

    asyncio.run(live_transcript.follow("call-1"))

    assert len(follower["written"]) == 1


def test_does_nothing_without_an_elevenlabs_key(monkeypatch):
    monkeypatch.setattr(live_transcript, "get_settings", lambda: Settings(_env_file=None, elevenlabs_api_key=""))
    live_transcript.start("call-1")  # would need a running event loop if it tried to follow
    assert not live_transcript._followers


def test_webhook_skips_lines_already_written_live():
    end = webhooks.CallEnd(
        call_id="call-1",
        conversation_id="conv-1",
        reason="completed",
        started_at=datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc),
        duration_seconds=20,
        lines=[Line("user", "Hello", 1), Line("agent", "Hi", 3), Line("user", "Bye", 9)],
    )
    after = datetime(2026, 10, 25, 17, 0, 15, tzinfo=timezone.utc)

    rows = webhooks.event_rows(end, after, agent="Maya", contact="Ivy", skip_lines=2, answered_already=True)

    assert [(kind, payload.get("text")) for _, kind, payload in rows] == [
        ("transcript_line", "Bye"),
        ("ended", "Call finished"),
    ]
    assert all(ts > after for ts, _, _ in rows)  # appended after the live lines
