import asyncio

import pytest
from google.genai import types

from app.contracts import TaskStatus
from app.orchestrator import runner, store
from app.tools.base import Tool
from tests.test_orchestrator_loop import FakeClient, call, model_says

class Recorded(list):
    previous: list


TASK = {
    "id": "task-1",
    "goal": "Book a table for 4",
    "status": "planning",
    "agent_id": "agent-1",
    "agent_name": "Maya",
    "persona": "Friendly and brief.",
    "tools": ["phone"],
    "user_name": "Demo User",
}


@pytest.fixture
def finished(monkeypatch):
    calls = Recorded()
    calls.previous = []

    async def load_task(task_id):
        return TASK

    async def recent_tasks(agent_id, before_task_id, limit=5):
        assert (agent_id, before_task_id) == ("agent-1", "task-1")
        return calls.previous

    async def finish_task(task_id, status, summary):
        calls.append((task_id, status, summary))

    monkeypatch.setattr(store, "load_task", load_task)
    monkeypatch.setattr(store, "recent_tasks", recent_tasks)
    monkeypatch.setattr(store, "finish_task", finish_task)
    return calls


def use_client(monkeypatch, client):
    monkeypatch.setattr(runner, "get_client", lambda: client)


def test_success_saves_gemini_summary(monkeypatch, finished):
    client = FakeClient(model_says(types.Part(text=" Booked for 18:00. ")))
    use_client(monkeypatch, client)

    asyncio.run(runner.run_task("task-1"))

    assert finished == [("task-1", TaskStatus.DONE, "Booked for 18:00.")]
    assert client.requests[0][0].parts[0].text == "Book a table for 4"


def test_gemini_error_marks_task_failed(monkeypatch, finished):
    class Broken:
        @property
        def aio(self):
            raise RuntimeError("503 overloaded")

    use_client(monkeypatch, Broken())

    asyncio.run(runner.run_task("task-1"))

    assert finished == [("task-1", TaskStatus.FAILED, runner.FAILED_SUMMARY)]


def test_paused_task_is_left_for_on_call_finished(monkeypatch, finished):
    async def place_call(**_):
        return {"call_id": "call-1"}

    tool = Tool("place_call", "Call.", {"type": "object"}, place_call, ends_turn=True)
    monkeypatch.setattr(runner, "TOOLS_BY_PERMISSION", {"phone": lambda task: [tool]})
    use_client(monkeypatch, FakeClient(model_says(call("place_call"))))

    asyncio.run(runner.run_task("task-1"))

    assert finished == []


def test_only_permitted_tools_are_declared(monkeypatch):
    phone, email = object(), object()
    monkeypatch.setattr(runner, "TOOLS_BY_PERMISSION", {"phone": lambda t: [phone], "email": lambda t: [email]})

    assert runner.tools_for({**TASK, "tools": ["phone", "payments"]}) == [phone]


def test_phone_permission_gives_both_call_tools():
    assert [t.name for t in runner.tools_for(TASK)] == ["lookup_contact", "place_call"]


def test_prompt_says_which_tools_exist():
    from app.orchestrator.prompts import build_system_prompt

    with_tools = build_system_prompt(agent_name="Maya", persona="", user_name="Alex", tool_names=["place_call"])
    without = build_system_prompt(agent_name="Maya", persona="", user_name="Alex", tool_names=[])

    assert "Your tools for this task: place_call" in with_tools
    assert "You have no tools for this task" in without


def test_earlier_tasks_come_before_the_new_message(monkeypatch, finished):
    finished.previous = [
        {"goal": "Book The Ivy for 4 at 6pm", "status": "failed", "summary": "Fully booked at 18:00; 20:30 offered."},
        {"goal": "What's my next booking?", "status": "done", "summary": "You have nothing booked yet."},
    ]
    client = FakeClient(model_says(types.Part(text="Calling The Ivy for 20:30.")))
    use_client(monkeypatch, client)

    asyncio.run(runner.run_task("task-1"))

    sent = [(c.role, c.parts[0].text) for c in client.requests[0]]
    assert sent == [
        ("user", "Book The Ivy for 4 at 6pm"),
        ("model", "(This task did not succeed.) Fully booked at 18:00; 20:30 offered."),
        ("user", "What's my next booking?"),
        ("model", "You have nothing booked yet."),
        ("user", "Book a table for 4"),
    ]


def test_long_summaries_are_cut(monkeypatch):
    contents = runner.history_contents([{"goal": "g", "status": "done", "summary": "x" * 5000}])
    assert len(contents[1].parts[0].text) == runner.MAX_SUMMARY_CHARS
