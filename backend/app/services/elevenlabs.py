"""ElevenLabs Conversational AI + Twilio outbound calls. Owner: Jamil.

start_call is the contract in app/contracts.py: it records the call, asks ElevenLabs to phone the
contact with the brief as dynamic variables, and returns our call_id at once. The post-call
webhook (routers/webhooks.py) later stores the transcript and resumes the task.
"""

import logging
from typing import Any

import httpx

from app import db
from app.config import get_settings
from app.contracts import CallBrief
from app.services import events, hang_up

log = logging.getLogger(__name__)

OUTBOUND_CALL_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"


class CallFailed(RuntimeError):
    pass


def dynamic_variables(brief: CallBrief, call_id: str) -> dict[str, str]:
    """Fills the {{placeholders}} in the ElevenLabs agent's prompt and first message."""
    return {
        "agent_name": brief.agent_name,
        "user_name": brief.user_name,
        # Spoken after "I'm calling to ...", so it must read as an action.
        "goal": brief.goal[:1].lower() + brief.goal[1:],
        "constraints": ", ".join(brief.constraints) or "none",
        "fallbacks": ", ".join(brief.fallbacks) or "none",
        # Not used by the prompt; comes back in the post-call webhook so we can find the call.
        "call_id": call_id,
    }


async def start_call(brief: CallBrief) -> str:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        # Local development without voice credentials keeps Alex's practice-run behaviour.
        from app.tools.phone import stand_in_start_call

        return await stand_in_start_call(brief)

    async with db.get_pool().connection() as conn, conn.transaction():
        row = await (
            await conn.execute(
                "INSERT INTO calls (task_id, to_number, business_name, status) VALUES (%s, %s, %s, 'dialing') RETURNING id",
                (brief.task_id, brief.to_number, brief.business_name or None),
            )
        ).fetchone()
        assert row is not None  # INSERT ... RETURNING always returns the new row
        call_id = str(row[0])
        text = f"Calling {brief.business_name}" if brief.business_name else "Calling"
        await events.emit(call_id, "dialing", {"text": text, "to_number": brief.to_number}, conn)

    try:
        result = await _place_outbound_call(settings, brief, call_id)
    except Exception as e:
        log.exception("Outbound call for call %s failed", call_id)
        await _mark_failed(call_id)
        raise CallFailed("The phone call could not be started.") from e

    async with db.get_pool().connection() as conn:
        await conn.execute(
            "UPDATE calls SET el_conversation_id = %s WHERE id = %s", (result.get("conversation_id"), call_id)
        )
    hang_up.remember(call_id, result.get("callSid"))  # lets the website's Hang up button end the call
    return call_id


async def _place_outbound_call(settings, brief: CallBrief, call_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            OUTBOUND_CALL_URL,
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={
                "agent_id": settings.elevenlabs_agent_id,
                "agent_phone_number_id": settings.elevenlabs_phone_number_id,
                "to_number": brief.to_number,
                "conversation_initiation_client_data": {"dynamic_variables": dynamic_variables(brief, call_id)},
            },
        )
    response.raise_for_status()
    result = response.json()
    if not result.get("success", True):
        raise CallFailed(result.get("message") or "ElevenLabs did not start the call.")
    return result


async def _mark_failed(call_id: str) -> None:
    async with db.get_pool().connection() as conn, conn.transaction():
        await conn.execute("UPDATE calls SET status = 'failed', ended_at = now() WHERE id = %s", (call_id,))
        await events.emit(
            call_id, "ended", {"text": "The call could not be started", "reason": "failed", "duration_seconds": 0}, conn
        )
