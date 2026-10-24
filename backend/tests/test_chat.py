import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.orchestrator import store
from app.routers import chat


@pytest.fixture
def client(monkeypatch):
    started = []

    async def fake_run_task(task_id):
        started.append(task_id)

    monkeypatch.setattr(chat, "run_task", fake_run_task)
    with TestClient(create_app(Settings(_env_file=None))) as c:
        c.started = started
        yield c


def fake_create_task(result=None, error=None):
    async def create_task(agent_id, message):
        if error:
            raise error
        create_task.calls.append((agent_id, message))
        return result

    create_task.calls = []
    return create_task


def test_chat_starts_task_in_background(client, monkeypatch):
    create = fake_create_task(result="task-1")
    monkeypatch.setattr(store, "create_task", create)

    response = client.post("/agents/agent-1/chat", json={"message": "  Book a table for 4  "})

    assert response.status_code == 202
    assert response.json() == {"task_id": "task-1"}
    assert create.calls == [("agent-1", "Book a table for 4")]
    assert client.started == ["task-1"]


@pytest.mark.parametrize(
    ("error", "code"),
    [(store.AgentNotFound("x"), 404), (store.AgentBusy("x"), 409)],
)
def test_chat_errors_are_readable(client, monkeypatch, error, code):
    monkeypatch.setattr(store, "create_task", fake_create_task(error=error))

    response = client.post("/agents/agent-1/chat", json={"message": "hi"})

    assert response.status_code == code
    assert isinstance(response.json()["detail"], str)
    assert client.started == []


def test_chat_rejects_empty_message(client):
    assert client.post("/agents/agent-1/chat", json={"message": "   "}).status_code == 422
