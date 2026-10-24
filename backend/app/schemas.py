"""Shared request/response models. The contract between Jamil, Alex and Evan:
change these together and regenerate the frontend client."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatResponse(BaseModel):
    task_id: str


class DayCalls(BaseModel):
    date: str  # YYYY-MM-DD, UK date
    calls: int


class AgentStats(BaseModel):
    name: str
    calls: int
    success_rate: float  # percent, 0-100


class Analytics(BaseModel):
    """Matches Analytics in frontend/src/types.ts."""

    total_calls: int
    success_rate: float  # percent of finished calls that booked (and weren't declined at the deposit)
    avg_duration_seconds: float
    calls_by_day: list[DayCalls]  # the last 7 days, oldest first
    agents: list[AgentStats]
