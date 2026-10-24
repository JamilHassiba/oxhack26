"""Chat with an agent: stores the message, creates a task and starts the orchestrator. Owner: Alex."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.orchestrator import store
from app.orchestrator.runner import run_task
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/agents/{agent_id}/chat", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED)
async def chat(agent_id: str, body: ChatRequest, background: BackgroundTasks) -> ChatResponse:
    """Starts a task for the message and returns its id at once; Gemini works on it in the background."""
    try:
        task_id = await store.create_task(agent_id, body.message)
    except store.AgentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found.") from None
    except store.AgentBusy:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This agent is still working on a task. Wait for it to finish, then send your next message.",
        ) from None
    background.add_task(run_task, task_id)
    return ChatResponse(task_id=task_id)
