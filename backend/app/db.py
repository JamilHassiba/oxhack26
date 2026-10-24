"""Postgres (Tiger Cloud) connection pool. Owner: Jamil.

Plain SQL via psycopg; the schema lives in backend/migrations/.
"""

import logging
from collections.abc import AsyncIterator

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def open_pool(database_url: str) -> None:
    global _pool
    _pool = AsyncConnectionPool(database_url, min_size=1, max_size=10, open=False)
    # Don't block startup on the DB: connections are made in the background and /health reports status.
    await _pool.open(wait=False)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database is not configured (DATABASE_URL is empty)")
    return _pool


async def get_conn() -> AsyncIterator[AsyncConnection]:
    """FastAPI dependency: `conn: AsyncConnection = Depends(get_conn)`."""
    async with get_pool().connection() as conn:
        yield conn


async def ping() -> str:
    """Returns "ok", "not_configured" or "error"."""
    if _pool is None:
        return "not_configured"
    try:
        async with _pool.connection(timeout=3) as conn:
            await conn.execute("SELECT 1")
        return "ok"
    except Exception:
        log.exception("Database ping failed")
        return "error"
