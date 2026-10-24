"""Confirmed calendar events and .ics export. Owner: Evan."""

from fastapi import APIRouter, Depends, Response
from app.evan.database import get_repository
from app.evan.ical import calendar_feed
from app.evan.models import CalendarEvent

router = APIRouter(tags=["calendar"])


@router.get("/calendar", response_model=list[CalendarEvent])
async def list_calendar(repo=Depends(get_repository, scope="function")):
    return await repo.calendar()


@router.get(
    "/calendar.ics",
    response_class=Response,
    responses={
        200: {
            "content": {"text/calendar": {"schema": {"type": "string"}}},
            "description": "Download an RFC 5545 calendar attachment",
        }
    },
)
async def download_calendar(repo=Depends(get_repository, scope="function")):
    return Response(
        calendar_feed(await repo.calendar()),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="concierge.ics"',
            "Cache-Control": "no-store",
        },
    )
