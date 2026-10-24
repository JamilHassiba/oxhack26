from fastapi import APIRouter, Request
from pydantic import BaseModel

from app import db

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    db: str  # ok | not_configured | error
    gemini: str  # configured | missing


@router.get("/health", response_model=Health)
async def health(request: Request) -> Health:
    settings = request.app.state.settings
    return Health(
        status="ok",
        db=await db.ping(),
        gemini="configured" if settings.gemini_api_key else "missing",
    )
