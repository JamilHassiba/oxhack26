"""Writes to the call_events hypertable (Tiger Data). Owner: Jamil.

Event kinds and payload shapes are defined in docs/EVENTS.md.
"""

from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app import db


async def emit(call_id: str, kind: str, payload: dict[str, Any], conn: AsyncConnection | None = None) -> None:
    """Appends one event. clock_timestamp(), not now(), so events in one transaction get distinct times."""
    sql = "INSERT INTO call_events (ts, call_id, kind, payload) VALUES (clock_timestamp(), %s, %s, %s)"
    params = (call_id, kind, Jsonb(payload))
    if conn is not None:
        await conn.execute(sql, params)
        return
    async with db.get_pool().connection() as own:
        await own.execute(sql, params)
