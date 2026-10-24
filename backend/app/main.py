"""FastAPI entrypoint: app setup, CORS, DB pool lifecycle and router registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import Settings, get_settings
from app.evan import register_routes
from app.routers import chat, health

logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.database_url:
            await db.open_pool(settings.database_url)
        yield
        await db.close_pool()

    app = FastAPI(title="Agent Concierge API", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    register_routes(app)
    app.include_router(chat.router)
    return app


app = create_app()
