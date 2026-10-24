"""Agent CRUD and archival. Owner: Evan; returns frontend/src/types.ts shapes."""

from uuid import UUID
from fastapi import APIRouter, Depends, Response
from app.evan.database import get_repository
from app.evan.models import Agent, AgentInput, AgentPatch

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[Agent])
async def list_agents(repo=Depends(get_repository, scope="function")):
    return await repo.agents()


@router.post("", response_model=Agent, status_code=201)
async def create_agent(
    body: AgentInput, repo=Depends(get_repository, scope="function")
):
    return await repo.create_agent(body)


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: UUID, repo=Depends(get_repository, scope="function")):
    return await repo.agent(agent_id)


@router.patch("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: UUID, body: AgentPatch, repo=Depends(get_repository, scope="function")
):
    return await repo.update_agent(agent_id, body)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: UUID, repo=Depends(get_repository, scope="function")):
    await repo.delete_agent(agent_id)
    return Response(status_code=204)
