"""Copies calendar events to the user's Google Calendar. Owner: Alex.

Uses a Google service account (a robot Google account) that the user has shared their calendar with
("Make changes to events"), so there is no sign-in screen. The event's description is filled in from the
call's outcome and the task's payments: name, details and deposit.

Without GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID it does nothing. A Google failure never fails
the booking: Gemini is told the event wasn't added.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import httpx
from psycopg.rows import dict_row

from app import db
from app.config import get_settings

log = logging.getLogger(__name__)

EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{}/events"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REMINDER_MINUTES = 60

_credentials = None  # cached: Google tokens last an hour and refresh themselves


def connected() -> bool:
    settings = get_settings()
    return bool(settings.google_service_account_file and settings.google_calendar_id)


async def add_event(event: dict[str, Any], task: dict[str, Any]) -> str:
    """Adds our calendar event to Google Calendar. Returns "added", "not_connected" or "failed"."""
    if not connected():
        return "not_connected"
    try:
        details = await booking_details(task["id"])
        body = event_body(event, task, details)
        await _insert(body)
    except Exception:
        log.exception("Adding calendar event %s to Google Calendar failed", event.get("id"))
        return "failed"
    return "added"


async def booking_details(task_id: str) -> dict[str, Any]:
    """The newest call's outcome and business name, plus the task's latest deposit."""
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """
            SELECT c.outcome, c.business_name,
                   (SELECT row_to_json(p) FROM (SELECT amount, currency, status FROM payments
                                                WHERE task_id = c.task_id ORDER BY created_at DESC LIMIT 1) p
                   ) AS payment
            FROM calls c WHERE c.task_id = %s ORDER BY c.started_at DESC LIMIT 1
            """,
            (task_id,),
        )
        return await cur.fetchone() or {}


def event_body(event: dict[str, Any], task: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    outcome = details.get("outcome") or {}
    payment = details.get("payment")
    venue = outcome.get("venue") or details.get("business_name")

    lines = []
    if outcome.get("booking_name"):
        lines.append(f"Name on booking: {outcome['booking_name']}")
    if outcome.get("details"):
        lines.append(f"Details: {outcome['details']}")
    if payment:
        status = {"paid": "paid", "denied": "declined", "pending_approval": "waiting for your approval"}
        lines.append(f"Deposit: £{payment['amount'] / 100:.2f} ({status.get(payment['status'], payment['status'])})")
    elif outcome.get("deposit_required") and outcome.get("deposit_amount_pence"):
        lines.append(f"Deposit: £{outcome['deposit_amount_pence'] / 100:.2f} (still to pay)")
    elif outcome:
        lines.append("Deposit: none")
    lines.append("")
    lines.append(f"Booked by {task['agent_name']} on a phone call, with Smart Connect.")
    if outcome.get("reason"):
        lines.append(outcome["reason"])

    return {
        # A uuid without dashes is a valid Google id; the same id twice is rejected, so a retry can't add it twice.
        "id": str(event["id"]).replace("-", ""),
        "summary": event["title"],
        "location": event.get("location") or venue or "",
        "description": "\n".join(lines),
        "start": {"dateTime": _iso(event["starts_at"]), "timeZone": "Europe/London"},
        "end": {"dateTime": _iso(event["ends_at"]), "timeZone": "Europe/London"},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": REMINDER_MINUTES}]},
    }


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


async def _insert(body: dict[str, Any]) -> None:
    token = await asyncio.to_thread(_access_token)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            EVENTS_URL.format(get_settings().google_calendar_id),
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
    if response.status_code == 409:  # already added by an earlier try
        return
    response.raise_for_status()


def _access_token() -> str:
    """Blocking (google-auth uses requests), so it runs in a thread."""
    global _credentials
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    if _credentials is None:
        with open(get_settings().google_service_account_file, encoding="utf-8") as f:
            _credentials = service_account.Credentials.from_service_account_info(json.load(f), scopes=SCOPES)
    if not _credentials.valid:
        _credentials.refresh(Request())
    return _credentials.token
