"""Joined task state and server-side per-agent history. Owner: Evan."""

from uuid import UUID
from fastapi import APIRouter, Depends
from app.evan.database import get_repository
from app.evan.models import Task

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}", response_model=Task, response_model_exclude_none=True)
async def get_task(task_id: UUID, repo=Depends(get_repository, scope="function")):
    return await repo.task(task_id)


@router.get(
    "/agents/{agent_id}/tasks",
    response_model=list[Task],
    response_model_exclude_none=True,
)
async def agent_tasks(agent_id: UUID, repo=Depends(get_repository, scope="function")):
    return await repo.tasks(agent_id)
