import asyncio

import pytest

from app.contracts import TaskStatus
from app.orchestrator import store
from app.tools import phone

TASK = {"id": "task-1", "agent_name": "Maya", "user_name": "Demo User", "tools": ["phone"]}
IVY = {"id": "c-1", "name": "The Ivy Oxford", "phone": "+447700900123"}


@pytest.fixture
def db(monkeypatch):
    """In-memory stand-ins for the store functions the phone tools use."""
    state = {"contacts": {"c-1": IVY}, "calls": 0, "status": None, "briefs": []}

    async def find_contacts(query, limit=5):
        return [
            {"contact_id": c["id"], "name": c["name"], "notes": ""}
            for c in state["contacts"].values()
            if query.lower() in c["name"].lower()
        ]

    async def list_contact_names():
        return [c["name"] for c in state["contacts"].values()]

    async def get_contact(contact_id):
        return state["contacts"].get(contact_id)

    async def count_calls(task_id):
        return state["calls"]

    async def set_task_status(task_id, status):
        state["status"] = status

    async def start_call(brief):
        state["briefs"].append(brief)
        state["calls"] += 1
        return "call-1"

    for fn in (find_contacts, list_contact_names, get_contact, count_calls, set_task_status):
        monkeypatch.setattr(store, fn.__name__, fn)
    monkeypatch.setattr(phone, "start_call", start_call)
    return state


def tool(name):
    return next(t for t in phone.phone_tools(TASK) if t.name == name)


def run(tool_name, **args):
    return asyncio.run(tool(tool_name).handler(**args))


def test_lookup_finds_contact_without_phone_number(db):
    result = run("lookup_contact", name="ivy")

    assert result == {"found": True, "contacts": [{"contact_id": "c-1", "name": "The Ivy Oxford", "notes": ""}]}
    assert "+44" not in str(result)


def test_lookup_miss_lists_known_contacts(db):
    assert run("lookup_contact", name="Nando's") == {"found": False, "known_contacts": ["The Ivy Oxford"]}


def test_place_call_builds_brief_and_marks_task_calling(db):
    result = run("place_call", contact_id="c-1", goal="Book a table for 4 at 18:00", fallbacks=["18:30"])

    assert result == {"status": "calling", "call_id": "call-1", "contact": "The Ivy Oxford"}
    assert db["status"] == TaskStatus.CALLING
    brief = db["briefs"][0]
    assert (brief.task_id, brief.to_number, brief.user_name, brief.agent_name) == (
        "task-1", "+447700900123", "Demo User", "Maya",
    )
    assert brief.fallbacks == ["18:30"] and brief.constraints == []
    assert tool("place_call").ends_turn


def test_place_call_unknown_contact_is_an_error(db):
    assert "error" in run("place_call", contact_id="nope", goal="Book")
    assert db["briefs"] == [] and db["status"] is None


def test_place_call_stops_after_max_calls(db):
    db["calls"] = phone.MAX_CALLS_PER_TASK
    assert "error" in run("place_call", contact_id="c-1", goal="Book")
    assert db["briefs"] == []
