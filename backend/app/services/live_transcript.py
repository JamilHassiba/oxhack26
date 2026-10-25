"""Live transcript for real phone calls. Owner: Alex.

ElevenLabs sends the transcript to our post-call webhook only when the call ends. While a call is in
progress, this follower asks ElevenLabs for the conversation so far every POLL_SECONDS and writes any new
lines as `transcript_line` events (plus `answered` with the first one), so the live stream
(GET /calls/{id}/events/stream) shows them during the call. The webhook then skips the lines already
written. Without an ElevenLabs key (local development, practice runs) it does nothing.

The newest turn may still be being spoken, so it is only stored once the next turn starts. Until then it
is kept in memory (speaking()) and the stream sends it as a `speaking` message, so the page shows it at once.
"""

import asyncio
import logging
import time
from typing import Any

import httpx
from psycopg.types.json import Jsonb

from app import db
from app.config import get_settings
from app.services.transcript import Line, transcript_lines

log = logging.getLogger(__name__)

CONVERSATION_URL = "https://api.elevenlabs.io/v1/convai/conversations/{}"
POLL_SECONDS = 1.0
MAX_SECONDS = 15 * 60  # calls are capped well below this
MAX_FAILURES = 10  # consecutive errors before giving up (the webhook still writes the transcript)
FINISHED = {"done", "failed"}

_followers: set[asyncio.Task] = set()  # keeps running followers from being garbage-collected
_speaking: dict[str, dict[str, str]] = {}  # call id -> the turn still being spoken: {"speaker", "text"}


def start(call_id: str) -> None:
    """Follows a just-started real call in the background. No-op without an ElevenLabs key."""
    if not get_settings().elevenlabs_api_key:
        return
    task = asyncio.create_task(follow(call_id))
    _followers.add(task)
    task.add_done_callback(_followers.discard)


def speaking(call_id: str) -> dict[str, str] | None:
    """The turn still being spoken on a live call, not stored yet. None between turns or after the call."""
    return _speaking.get(call_id)


async def call_state(call_id: str) -> tuple[str | None, bool]:
    """(ElevenLabs conversation id or None, whether the call has ended)."""
    async with db.get_pool().connection() as conn:
        row = await (
            await conn.execute("SELECT el_conversation_id, ended_at IS NOT NULL FROM calls WHERE id = %s", (call_id,))
        ).fetchone()
    return (row[0], row[1]) if row else (None, True)


async def fetch_conversation(client: httpx.AsyncClient, conversation_id: str) -> dict[str, Any]:
    response = await client.get(
        CONVERSATION_URL.format(conversation_id),
        headers={"xi-api-key": get_settings().elevenlabs_api_key},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


async def write_new_lines(call_id: str, lines: list[Line]) -> tuple[str, str] | None:
    """Writes the lines not stored yet. Returns the (agent, business) speaker names, or None once the call
    has ended (the webhook took over)."""
    async with db.get_pool().connection() as conn, conn.transaction():
        # Same lock as the webhook's, so the two never write the same lines.
        row = await (
            await conn.execute(
                """
                SELECT c.ended_at, a.name,
                       c.business_name,
                       (SELECT count(*) FROM call_events WHERE call_id = c.id AND kind = 'transcript_line'),
                       EXISTS (SELECT 1 FROM call_events WHERE call_id = c.id AND kind = 'answered')
                FROM calls c JOIN tasks t ON t.id = c.task_id JOIN agents a ON a.id = t.agent_id
                WHERE c.id = %s
                FOR UPDATE OF c
                """,
                (call_id,),
            )
        ).fetchone()
        if row is None or row[0] is not None:
            return None
        _, agent, contact, written, answered = row
        names = (agent, contact or "Restaurant")
        new = lines[written:]
        if new and not answered:
            await _event(conn, call_id, "answered", {"text": "Connected"})
        for line in new:
            await _event(conn, call_id, "transcript_line", {"speaker": speaker(line, names), "text": line.text})
    return names


def speaker(line: Line, names: tuple[str, str]) -> str:
    return names[0] if line.role == "agent" else names[1]


async def _event(conn, call_id: str, kind: str, payload: dict[str, Any]) -> None:
    # clock_timestamp(): distinct, real arrival times (docs/EVENTS.md rule 3).
    await conn.execute(
        "INSERT INTO call_events (ts, call_id, kind, payload) VALUES (clock_timestamp(), %s, %s, %s)",
        (call_id, kind, Jsonb(payload)),
    )


async def follow(call_id: str) -> None:
    try:
        await _follow(call_id)
    finally:
        _speaking.pop(call_id, None)


async def _follow(call_id: str) -> None:
    deadline, failures = time.monotonic() + MAX_SECONDS, 0
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline and failures < MAX_FAILURES:
            await asyncio.sleep(POLL_SECONDS)
            try:
                conversation_id, ended = await call_state(call_id)
                if ended:
                    return
                if not conversation_id:
                    continue  # start_call sets it right after ElevenLabs accepts the call
                conversation = await fetch_conversation(client, conversation_id)
                lines = transcript_lines(conversation.get("transcript") or [])
                finished = conversation.get("status") in FINISHED
                # The newest turn may still be being spoken, and a line once written is never rewritten (the
                # webhook skips lines already stored). So write it only once the next turn has started.
                names = await write_new_lines(call_id, lines if finished else lines[:-1])
                if names is None or finished:
                    return
                if lines:
                    _speaking[call_id] = {"speaker": speaker(lines[-1], names), "text": lines[-1].text}
                failures = 0
            except Exception:
                failures += 1
                log.warning("Live transcript for call %s: poll failed (%d in a row)", call_id, failures, exc_info=True)
    log.info("Live transcript for call %s: stopped following", call_id)
