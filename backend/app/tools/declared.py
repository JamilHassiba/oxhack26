"""Gemini declarations for the calendar and email functions. Owner: Alex.

task_id is bound here, never chosen by Gemini. The calendar is the user's Google Calendar (services/google_calendar.py).
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.services import google_calendar
from app.tools.base import Tool
from app.tools.email import send_email

UK = ZoneInfo("Europe/London")


def uk_time(value: str) -> str:
    """Gemini gives UK wall-clock time; we attach the right offset ourselves (it gets BST/GMT changes wrong)."""
    return datetime.fromisoformat(value).replace(tzinfo=UK).isoformat()


def calendar_tools(task: dict[str, Any]) -> list[Tool]:
    async def add_event(title: str, starts_at: str, ends_at: str, location: str = "") -> dict:
        starts_at, ends_at = uk_time(starts_at), uk_time(ends_at)
        if datetime.fromisoformat(ends_at) <= datetime.fromisoformat(starts_at):
            return {"error": "The event must end after it starts."}
        # The task id as the event id: one event per task, so a retry can't add it twice.
        event = {"id": task["id"], "title": title, "starts_at": starts_at, "ends_at": ends_at, "location": location}
        result = await google_calendar.add_event(event, task)
        if result == "not_connected":
            return {"error": "Google Calendar isn't connected, so the event wasn't added."}
        if result == "failed":
            return {"error": "Adding the event to Google Calendar failed."}
        return {"added": True, **event}

    return [
        Tool(
            name="create_calendar_event",
            description="Add an event to the user's calendar.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "e.g. 'Dinner at The Ivy Oxford (table for 4)'."},
                    "starts_at": {"type": "string", "description": "UK local time, e.g. 2026-10-25T18:00."},
                    "ends_at": {"type": "string", "description": "UK local time, after starts_at."},
                    "location": {"type": "string", "description": "Place name or address."},
                },
                "required": ["title", "starts_at", "ends_at"],
            },
            handler=add_event,
        )
    ]


def email_tools(task: dict[str, Any]) -> list[Tool]:
    async def email_user(subject: str, body: str) -> dict:
        return await send_email(task_id=task["id"], subject=subject, body=body)

    return [
        Tool(
            name="send_email",
            description="Email the user, e.g. a booking confirmation. It always goes to the user; you can't choose the recipient.",
            parameters={
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "One line, under 200 characters."},
                    "body": {"type": "string", "description": "Plain text."},
                },
                "required": ["subject", "body"],
            },
            handler=email_user,
        )
    ]
