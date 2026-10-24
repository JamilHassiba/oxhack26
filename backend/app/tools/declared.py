"""Gemini declarations for Evan's calendar and email functions: he writes them, we declare them. Owner: Alex.

task_id is bound here, never chosen by Gemini. Evan's functions check the agent's permission themselves too.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.tools.base import Tool
from app.tools.calendar import create_calendar_event
from app.tools.email import send_email

UK = ZoneInfo("Europe/London")


def uk_time(value: str) -> str:
    """Gemini gives UK wall-clock time; we attach the right offset ourselves (it gets BST/GMT changes wrong)."""
    return datetime.fromisoformat(value).replace(tzinfo=UK).isoformat()


def calendar_tools(task: dict[str, Any]) -> list[Tool]:
    async def add_event(title: str, starts_at: str, ends_at: str, location: str = "") -> dict:
        return await create_calendar_event(
            task_id=task["id"], title=title, starts_at=uk_time(starts_at), ends_at=uk_time(ends_at), location=location
        )

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
