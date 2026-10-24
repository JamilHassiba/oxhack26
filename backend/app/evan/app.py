"""Deployable smoke/API app until Alex's main app is merged. No orchestrator is fabricated."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.evan import register_routes
from app.evan.database import close_fallback_pool, open_fallback_pool, pool
from app.evan.settings import get_settings


def create_app(settings=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        await open_fallback_pool(settings.database_url.get_secret_value())
        yield
        await close_fallback_pool()

    app = FastAPI(title="Concierge API", lifespan=lifespan)
    register_routes(app)

    @app.get("/health")
    async def health():
        status = "not_configured"
        try:
            async with pool().connection(timeout=3) as conn:
                await conn.execute("SELECT 1")
            status = "ok"
        except Exception:
            pass
        return {
            "status": "ok",
            "db": status,
            "scope": "agents/tasks/calendar; chat and voice pending shared app integration",
        }

    return app


app = create_app()
