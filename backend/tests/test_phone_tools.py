import asyncio

import pytest

from app.config import Settings
from app.contracts import TaskStatus
from app.orchestrator import store
from app.tools import phone

TASK = {"id": "task-1", "agent_name": "Maya", "user_name": "Demo User", "tools": ["phone"]}
NUMBER = "+447700900123"


@pytest.fixture
def db(monkeypatch):
    """In-memory stand-ins for the store functions the phone tool uses, and a configured CALL_NUMBER."""
    state = {"calls": 0, "status": None, "briefs": []}

    async def count_calls(task_id):
        return state["calls"]

    async def set_task_status(task_id, status):
        state["status"] = status

    async def start_call(brief):
        state["briefs"].append(brief)
        state["calls"] += 1
        return "call-1"

    for fn in (count_calls, set_task_status):
        monkeypatch.setattr(store, fn.__name__, fn)
    monkeypatch.setattr(phone, "start_call", start_call)
    # Tests never read the real .env.
    monkeypatch.setattr(phone, "get_settings", lambda: Settings(_env_file=None, call_number=NUMBER))
    return state


def tool(name):
    return next(t for t in phone.phone_tools(TASK) if t.name == name)


def run(tool_name, **args):
    return asyncio.run(tool(tool_name).handler(**args))


def test_place_call_only_offers_place_call():
    assert [t.name for t in phone.phone_tools(TASK)] == ["place_call"]


def test_place_call_rings_the_call_number_for_any_business(db):
    result = run("place_call", business_name=" Dishoom ", goal="Book a table for 4 at 18:00", fallbacks=["18:30"])

    assert result == {"status": "calling", "call_id": "call-1", "business": "Dishoom"}
    assert db["status"] == TaskStatus.CALLING
    brief = db["briefs"][0]
    assert (brief.task_id, brief.to_number, brief.business_name, brief.user_name, brief.agent_name) == (
        "task-1", NUMBER, "Dishoom", "Demo User", "Maya",
    )
    assert brief.fallbacks == ["18:30"] and brief.constraints == []
    assert tool("place_call").ends_turn


def test_place_call_needs_a_business_name(db):
    assert "error" in run("place_call", business_name="  ", goal="Book")
    assert db["briefs"] == [] and db["status"] is None


def test_place_call_without_a_configured_number_is_an_error(db, monkeypatch):
    monkeypatch.setattr(phone, "get_settings", lambda: Settings(_env_file=None, call_number=""))
    assert "error" in run("place_call", business_name="Dishoom", goal="Book")
    assert db["briefs"] == []


def test_place_call_stops_after_max_calls(db):
    db["calls"] = phone.MAX_CALLS_PER_TASK
    assert "error" in run("place_call", business_name="Dishoom", goal="Book")
    assert db["briefs"] == []


def test_fake_call_end_scenarios_fill_in_names():
    from scripts.fake_call_end import SCENARIOS

    assert SCENARIOS["no_answer"] == []
    for lines in SCENARIOS.values():
        for speaker, text in lines:
            assert speaker in {"agent", "restaurant"}
            text.format(goal="g", user="u", contact="c")
