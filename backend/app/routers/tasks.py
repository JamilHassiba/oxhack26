"""Each agent's tasks, joined with their latest call and payment. Owner: Evan."""

from uuid import UUID
from fastapi import APIRouter, Depends
from app.evan.database import get_repository
from app.evan.models import Task

router = APIRouter(tags=["tasks"])


@router.get(
    "/agents/{agent_id}/tasks",
    response_model=list[Task],
    response_model_exclude_none=True,
)
async def agent_tasks(agent_id: UUID, repo=Depends(get_repository, scope="function")):
    return await repo.tasks(agent_id)
