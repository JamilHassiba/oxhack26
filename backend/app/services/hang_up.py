"""Hang up a call from the website's Hang up button. Owner: Alex.

ElevenLabs has no "end this call" API, but its outbound-call response includes Twilio's callSid, and
Twilio ends a call when we set its status. ElevenLabs then sends its normal post-call webhook, which
saves the transcript so far and finishes the task. If that webhook hasn't arrived after
WEBHOOK_WAIT_SECONDS, or for practice calls (no ElevenLabs key), we end the call ourselves.

The outcome is saved first as "you hung up", so on_call_finished uses it instead of reading the
transcript, and doesn't phone the business again.
"""

import asyncio
import logging

import httpx
from psycopg.types.json import Jsonb

from app import db
from app.config import get_settings

log = logging.getLogger(__name__)

TWILIO_CALL_URL = "https://api.twilio.com/2010-04-01/Accounts/{}/Calls/{}.json"
WEBHOOK_WAIT_SECONDS = 90.0
HUNG_UP_REASON = "You hung up the call before it finished."
HUNG_UP_OUTCOME = {
    "result": "other",
    "booked": False,
    "starts_at": None,
    "party_size": None,
    "booking_name": None,
    "venue": None,
    "deposit_required": False,
    "deposit_amount_pence": None,
    "offered_times": [],
    "reason": HUNG_UP_REASON,
}

# Our call id -> Twilio callSid. In memory: hanging up only matters while a call is live, and the API
# runs as one process.
_call_sids: dict[str, str] = {}
_background: set[asyncio.Task] = set()


class CallNotFound(Exception):
    pass


class CallAlreadyEnded(Exception):
    pass


class HangUpUnavailable(Exception):
    pass


class HangUpFailed(Exception):
    pass


def remember(call_id: str, call_sid: str | None) -> None:
    """Called by start_call with the callSid from ElevenLabs' outbound-call response."""
    if call_sid:
        _call_sids[call_id] = call_sid


async def call_ended(call_id: str) -> bool | None:
    """Whether the call has ended, or None if there is no such call."""
    async with db.get_pool().connection() as conn:
        row = await (await conn.execute("SELECT ended_at FROM calls WHERE id::text = %s", (call_id,))).fetchone()
    return None if row is None else row[0] is not None


async def hang_up(call_id: str) -> None:
    settings = get_settings()
    ended = await call_ended(call_id)
    if ended is None:
        raise CallNotFound
    if ended:
        raise CallAlreadyEnded

    if not settings.elevenlabs_api_key:  # practice run: nobody was dialled, so just end it
        await _save_outcome(call_id)
        _in_background(end_ourselves(call_id))
        return

    call_sid = _call_sids.get(call_id)
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise HangUpUnavailable("Hanging up isn't set up yet (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are missing).")
    if not call_sid:
        raise HangUpUnavailable("This call can't be hung up from here. Hang up on the phone instead.")

    await _save_outcome(call_id)
    try:
        await _end_twilio_call(settings, call_sid)
    except Exception as e:
        log.exception("Hanging up call %s (Twilio %s) failed", call_id, call_sid)
        await _clear_outcome(call_id)
        raise HangUpFailed("The call couldn't be hung up. Try again, or hang up on the phone.") from e
    _call_sids.pop(call_id, None)
    _in_background(_end_if_no_webhook(call_id))


async def _end_twilio_call(settings, call_sid: str) -> None:
    """`completed` ends an answered call; a call that is still ringing needs `canceled`."""
    url = TWILIO_CALL_URL.format(settings.twilio_account_sid, call_sid)
    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, auth=auth, data={"Status": "completed"})
        response.raise_for_status()
        if response.json().get("status") in ("queued", "ringing"):
            response = await client.post(url, auth=auth, data={"Status": "canceled"})
            response.raise_for_status()


async def _save_outcome(call_id: str) -> None:
    async with db.get_pool().connection() as conn:
        await conn.execute("UPDATE calls SET outcome = %s WHERE id::text = %s", (Jsonb(HUNG_UP_OUTCOME), call_id))


async def _clear_outcome(call_id: str) -> None:
    async with db.get_pool().connection() as conn:
        await conn.execute(
            "UPDATE calls SET outcome = NULL WHERE id::text = %s AND ended_at IS NULL AND outcome->>'reason' = %s",
            (call_id, HUNG_UP_REASON),
        )


async def _end_if_no_webhook(call_id: str) -> None:
    await asyncio.sleep(WEBHOOK_WAIT_SECONDS)
    await end_ourselves(call_id)


async def end_ourselves(call_id: str) -> None:
    """Marks the call ended (keeping any live transcript lines) and finishes the task, unless the
    post-call webhook already did."""
    async with db.get_pool().connection() as conn, conn.transaction():
        row = await (
            await conn.execute(
                """
                SELECT c.ended_at, extract(epoch FROM now() - c.started_at)::int,
                       COALESCE((SELECT jsonb_agg(jsonb_build_object('speaker', payload->>'speaker',
                                                                     'text', payload->>'text') ORDER BY ts)
                                 FROM call_events WHERE call_id = c.id AND kind = 'transcript_line'), '[]')
                FROM calls c WHERE c.id::text = %s
                FOR UPDATE OF c
                """,
                (call_id,),
            )
        ).fetchone()
        if row is None or row[0] is not None:
            return
        _, seconds, transcript = row
        await conn.execute(
            "UPDATE calls SET status = 'ended', ended_at = now(), transcript = %s WHERE id::text = %s",
            (Jsonb(transcript), call_id),
        )
        await conn.execute(
            "INSERT INTO call_events (ts, call_id, kind, payload) VALUES (clock_timestamp(), %s, 'ended', %s)",
            (call_id, Jsonb({"text": "You hung up", "reason": "completed", "duration_seconds": seconds})),
        )
    # Imported here: start_call imports this module, and the orchestrator imports start_call.
    from app.orchestrator.callbacks import on_call_finished

    try:
        await on_call_finished(call_id)
    except Exception:
        log.exception("on_call_finished(%s) failed after hanging up", call_id)


def _in_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)
