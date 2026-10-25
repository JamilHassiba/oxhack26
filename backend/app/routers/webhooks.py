"""ElevenLabs webhooks: post-call transcript and mid-call server tools. Owner: Jamil.

POST /webhooks/elevenlabs/post-call receives ElevenLabs' post-call webhook. It checks the signature,
saves the transcript and outcome on our calls row and the matching call_events (docs/EVENTS.md), then
hands over to Alex's on_call_finished. It answers at once and finishes the task in the background, so
ElevenLabs never times out and retries while Gemini is working.
"""

import hashlib
import hmac
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from psycopg.types.json import Jsonb

from app import db
from app.config import get_settings
from app.orchestrator.callbacks import on_call_finished

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/elevenlabs", tags=["webhooks"])

SIGNATURE_TOLERANCE_SECONDS = 30 * 60
# Voice-model direction tags like "[happy]" or "[calm]" that the expressive voice adds to the agent's text.
EMOTION_TAG = re.compile(r"\[[a-zA-Z ]+\]\s*")
# ElevenLabs' call_initiation_failure reasons -> our `ended` reasons and calls.status.
FAILURE_REASONS = {"no-answer": "no_answer", "busy": "busy"}
ENDED_TEXT = {
    "completed": "Call finished",
    "no_answer": "No answer",
    "busy": "Line busy",
    "voicemail": "Went to voicemail",
    "failed": "The call could not be connected",
}
CALL_STATUS = {"completed": "ended"}  # otherwise calls.status is the reason itself


class InvalidSignature(Exception):
    pass


def verify_signature(body: bytes, header: str | None, secret: str, now: float | None = None) -> None:
    """ElevenLabs signs `{timestamp}.{body}` with HMAC-SHA256; the header is `t=<timestamp>,v0=<hex>`."""
    if not header:
        raise InvalidSignature("missing signature header")
    parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    timestamp, signature = parts.get("t", ""), parts.get("v0", "")
    if not timestamp.isdigit() or not signature:
        raise InvalidSignature("malformed signature header")
    if abs((now or time.time()) - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
        raise InvalidSignature("signature too old")
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidSignature("signature mismatch")


@dataclass
class Line:
    role: str  # "agent" or "user" (the business)
    text: str
    seconds: float  # into the call


@dataclass
class CallEnd:
    """What we keep from one ElevenLabs webhook."""

    call_id: str | None
    conversation_id: str | None
    reason: str  # an EVENTS.md `ended` reason
    started_at: datetime | None
    duration_seconds: int
    lines: list[Line] = field(default_factory=list)
    summary: str | None = None


def parse_webhook(payload: dict[str, Any]) -> CallEnd | None:
    """Turns an ElevenLabs webhook into a CallEnd, or None for webhook types we don't use."""
    kind, data = payload.get("type"), payload.get("data") or {}
    client_data = data.get("conversation_initiation_client_data") or {}
    call_id = (client_data.get("dynamic_variables") or {}).get("call_id")
    metadata = data.get("metadata") or {}
    start = metadata.get("start_time_unix_secs")
    started_at = datetime.fromtimestamp(start, timezone.utc) if start else None

    if kind == "call_initiation_failure":
        reason = FAILURE_REASONS.get(str(data.get("failure_reason")), "failed")
        return CallEnd(call_id, data.get("conversation_id"), reason, started_at, 0)
    if kind != "post_call_transcription":
        return None

    lines = []
    for turn in data.get("transcript") or []:
        text = turn.get("message") or ""
        if turn.get("role") == "agent":
            text = EMOTION_TAG.sub("", text)
        if text.strip():
            lines.append(Line(turn.get("role") or "user", text.strip(), float(turn.get("time_in_call_secs") or 0)))
    return CallEnd(
        call_id=call_id,
        conversation_id=data.get("conversation_id"),
        reason="completed",
        started_at=started_at,
        duration_seconds=int(metadata.get("call_duration_secs") or 0),
        lines=lines,
        summary=(data.get("analysis") or {}).get("transcript_summary"),
    )


def event_rows(end: CallEnd, after: datetime, agent: str, contact: str) -> list[tuple[datetime, str, dict]]:
    """The call's events at their real times in the call, each strictly after the previous one."""
    base = max(end.started_at or after, after)
    rows: list[tuple[datetime, str, dict]] = []

    def add(offset: float, kind: str, payload: dict) -> None:
        ts = base + timedelta(seconds=offset)
        if rows and ts <= rows[-1][0]:
            ts = rows[-1][0] + timedelta(milliseconds=1)
        elif not rows and ts <= after:
            ts = after + timedelta(milliseconds=1)
        rows.append((ts, kind, payload))

    if end.reason == "completed":
        add(0, "answered", {"text": "Connected"})
    for line in end.lines:
        speaker = agent if line.role == "agent" else contact
        add(line.seconds, "transcript_line", {"speaker": speaker, "text": line.text})
    add(end.duration_seconds, "ended", {
        "text": ENDED_TEXT[end.reason], "reason": end.reason, "duration_seconds": end.duration_seconds,
    })
    return rows


async def save_call_end(end: CallEnd) -> str | None:
    """Stores the transcript and events on our call. Returns its id, or None if there's nothing to do."""
    async with db.get_pool().connection() as conn, conn.transaction():
        row = await (
            await conn.execute(
                """
                SELECT c.id::text, c.ended_at,
                       (SELECT max(ts) FROM call_events WHERE call_id = c.id),
                       a.name,
                       (SELECT name FROM contacts WHERE phone = c.to_number ORDER BY created_at LIMIT 1)
                FROM calls c JOIN tasks t ON t.id = c.task_id JOIN agents a ON a.id = t.agent_id
                WHERE c.id::text = %s OR c.el_conversation_id = %s
                FOR UPDATE OF c
                """,
                (end.call_id or "", end.conversation_id or ""),
            )
        ).fetchone()
        if row is None:
            log.info("Post-call webhook for unknown call (conversation %s): ignored", end.conversation_id)
            return None
        call_id, ended_at, last_event_at, agent, contact = row
        if ended_at is not None:
            log.info("Post-call webhook for call %s, which already ended: ignored", call_id)
            return None

        contact = contact or "Restaurant"
        transcript = [
            {"speaker": agent if line.role == "agent" else contact, "text": line.text} for line in end.lines
        ]
        await conn.execute(
            """
            UPDATE calls SET status = %s, ended_at = now(), transcript = %s, summary = %s,
                             el_conversation_id = COALESCE(el_conversation_id, %s)
            WHERE id = %s
            """,
            (CALL_STATUS.get(end.reason, end.reason), Jsonb(transcript), end.summary, end.conversation_id, call_id),
        )
        after = last_event_at or datetime.now(timezone.utc)
        for ts, kind, payload in event_rows(end, after, agent, contact):
            await conn.execute(
                "INSERT INTO call_events (ts, call_id, kind, payload) VALUES (%s, %s, %s, %s)",
                (ts, call_id, kind, Jsonb(payload)),
            )
    return call_id


async def finish(call_id: str) -> None:
    try:
        await on_call_finished(call_id)
    except Exception:
        log.exception("on_call_finished(%s) failed after the post-call webhook", call_id)


@router.post("/post-call")
async def post_call(request: Request, background: BackgroundTasks) -> dict:
    secret = get_settings().elevenlabs_webhook_secret
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ELEVENLABS_WEBHOOK_SECRET is not configured.")
    body = await request.body()
    try:
        verify_signature(body, request.headers.get("elevenlabs-signature"), secret)
    except InvalidSignature as e:
        log.warning("Rejected post-call webhook: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature.") from None

    end = parse_webhook(json.loads(body))
    if end is None:
        return {"status": "ignored"}
    call_id = await save_call_end(end)
    if call_id is None:
        return {"status": "ignored"}
    background.add_task(finish, call_id)
    return {"status": "ok", "call_id": call_id}
