from datetime import datetime, timezone

from app.routers import webhooks
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
