"""Use Jamil's shared pool when present; provide an isolated smoke-app pool otherwise."""

from contextlib import asynccontextmanager
from fastapi import HTTPException
from psycopg_pool import AsyncConnectionPool, PoolTimeout

_fallback_pool = None


def pool():
    from app import db

    provider = getattr(db, "get_pool", None)
    if provider:
        try:
            return provider()
        except RuntimeError:
            pass
    if _fallback_pool is None:
        raise HTTPException(
            503, "Database is not configured. Set DATABASE_URL and run migrations."
        )
    return _fallback_pool


async def open_fallback_pool(url):
    global _fallback_pool
    if url:
        _fallback_pool = AsyncConnectionPool(url, min_size=1, max_size=5, open=False)
        await _fallback_pool.open(wait=False)


async def close_fallback_pool():
    global _fallback_pool
    if _fallback_pool is not None:
        await _fallback_pool.close()
        _fallback_pool = None


@asynccontextmanager
async def connection():
    try:
        async with pool().connection(timeout=5) as conn:
            yield conn
    except PoolTimeout as exc:
        raise HTTPException(503, "Database is temporarily unavailable.") from exc


async def get_repository():
    from app.evan.repository import Repository

    async with connection() as conn:
        yield Repository(conn)
