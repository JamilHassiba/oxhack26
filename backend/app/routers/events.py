"""Server-sent events stream of call_events for the live call view. Owner: Jamil (built by Alex).

GET /calls/{id}/events/stream, as in docs/EVENTS.md: sends the call's existing events first, then new ones
as they're written, one SSE message per event (`event: <kind>`, `id: <ts>`, `data: <row JSON>`), and
closes after `ended`. The browser resumes after a reconnect with Last-Event-ID. Rows are read by short
polling, which is plenty for one demo call at a time.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from psycopg.rows import dict_row
from sse_starlette import EventSourceResponse, ServerSentEvent

from app import db
from app.evan.models import CallEvent

router = APIRouter(tags=["events"])

POLL_SECONDS = 1.0
PING_SECONDS = 15
MAX_STREAM_SECONDS = 30 * 60  # calls are capped well below this; stops a forgotten tab polling forever


async def call_exists(call_id: str) -> bool:
    async with db.get_pool().connection() as conn:
        return await (await conn.execute("SELECT 1 FROM calls WHERE id = %s", (call_id,))).fetchone() is not None


async def events_after(call_id: str, after: datetime | None) -> list[dict[str, Any]]:
    """The call's events after `after` (all of them if None), oldest first. ts is unique per call."""
    query = "SELECT ts, call_id::text AS call_id, kind, payload FROM call_events WHERE call_id = %s"
    params: tuple = (call_id,)
    if after is not None:
        query += " AND ts > %s"
        params += (after,)
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(query + " ORDER BY ts", params)
        return await cur.fetchall()


async def ended_by(call_id: str, at: datetime) -> bool:
    async with db.get_pool().connection() as conn:
        row = await (
            await conn.execute(
                "SELECT 1 FROM call_events WHERE call_id = %s AND kind = 'ended' AND ts <= %s LIMIT 1", (call_id, at)
            )
        ).fetchone()
    return row is not None


def parse_event_id(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("/calls/{call_id}/events/stream", response_model=None)
async def call_event_stream(
    call_id: str, request: Request, last_event_id: str | None = Header(default=None)
) -> EventSourceResponse | Response:
    try:
        UUID(call_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found.") from None
    if not await call_exists(call_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found.")

    since = parse_event_id(last_event_id)
    if since is not None and await ended_by(call_id, since):
        # The browser already has everything up to `ended`. 204 tells EventSource to stop reconnecting.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def stream() -> AsyncIterator[ServerSentEvent]:
        last, deadline = since, time.monotonic() + MAX_STREAM_SECONDS
        while time.monotonic() < deadline and not await request.is_disconnected():
            for row in await events_after(call_id, last):
                last = row["ts"]
                event = CallEvent.model_validate(row)
                # Same model and JSON as task.events from GET /tasks/{id} (which omits empty fields): the UI
                # de-duplicates stream events against those by comparing ts, kind and the payload JSON.
                yield ServerSentEvent(
                    data=event.model_dump_json(exclude_none=True), event=event.kind, id=row["ts"].isoformat()
                )
                if event.kind == "ended":
                    return
            await asyncio.sleep(POLL_SECONDS)

    return EventSourceResponse(stream(), ping=PING_SECONDS)
