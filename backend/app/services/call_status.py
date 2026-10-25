"""Ringing and answered for real phone calls. Owner: Jamil.

ElevenLabs tells us nothing until the call ends, but Twilio knows the call's status. While a call is
live, this asks Twilio for it every POLL_SECONDS and writes a `ringing` event when the phone rings and
an `answered` event when it's picked up, so the website can show where the call is up to. The post-call
webhook doesn't write `answered` again if it's already there. Without Twilio credentials it does nothing.
"""

import asyncio
import logging
import time

import httpx

from app.config import get_settings
from app.services import events
from app.services.hang_up import TWILIO_CALL_URL, call_ended

log = logging.getLogger(__name__)

POLL_SECONDS = 1.0
MAX_SECONDS = 5 * 60  # long enough for any ringing; stops once answered or ended
DONE = {"completed", "busy", "failed", "no-answer", "canceled"}

_followers: set[asyncio.Task] = set()  # keeps running followers from being garbage-collected


def start(call_id: str, call_sid: str | None) -> None:
    settings = get_settings()
    if not (call_sid and settings.twilio_account_sid and settings.twilio_auth_token):
        return
    task = asyncio.create_task(follow(call_id, call_sid))
    _followers.add(task)
    task.add_done_callback(_followers.discard)


async def fetch_status(client: httpx.AsyncClient, call_sid: str) -> str | None:
    settings = get_settings()
    response = await client.get(
        TWILIO_CALL_URL.format(settings.twilio_account_sid, call_sid),
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("status")


async def follow(call_id: str, call_sid: str) -> None:
    rang, deadline = False, time.monotonic() + MAX_SECONDS
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_SECONDS)
            try:
                if await call_ended(call_id) is not False:
                    return
                status = await fetch_status(client, call_sid)
            except Exception:
                log.warning("Call status for call %s: Twilio poll failed", call_id, exc_info=True)
                continue
            if status == "ringing" and not rang:
                rang = True
                await events.emit(call_id, "ringing", {"text": "Ringing"})
            elif status == "in-progress":
                await events.emit(call_id, "answered", {"text": "Connected"})
                return
            elif status in DONE:
                return
