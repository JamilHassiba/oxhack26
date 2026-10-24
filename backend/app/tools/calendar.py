"""Evan's calendar tool. Alex binds task_id when declaring it to Gemini."""

from uuid import UUID
from app.evan.database import connection
from app.evan.models import CalendarInput
from app.evan.repository import Repository


async def create_calendar_event(
    *, task_id: str, title: str, starts_at: str, ends_at: str, location: str = ""
) -> dict:
    """Create one event for a task; timezone offsets are required. Identical retries reuse it."""
    task_uuid = UUID(task_id)
    data = CalendarInput(
        title=title, starts_at=starts_at, ends_at=ends_at, location=location
    )
    async with connection() as conn:
        event = await Repository(conn).create_calendar_event(task_uuid, data)
        return event.model_dump(mode="json")
