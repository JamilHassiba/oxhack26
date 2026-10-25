import asyncio

import pytest
from google.genai import types

from app.contracts import TaskStatus
from app.orchestrator import callbacks, store
from app.tools import declared
from tests.test_orchestrator_loop import FakeClient, call, model_says

BOOKED = {
    "result": "booked",
    "booked": True,
    "starts_at": "2026-10-25T18:00:00+00:00",
    "details": "table for 4",
    "deposit_required": False,
    "deposit_amount_pence": None,
    "offered_times": [],
    "reason": "Booked for 18:00.",
}
FULL = {
    **BOOKED,
    "result": "fully_booked",
    "booked": False,
    "starts_at": None,
    "offered_times": ["2026-10-25T20:30"],
    "reason": "Fully booked at 18:00; 20:30 offered.",
}
NO_ANSWER = {**FULL, "result": "no_answer", "offered_times": [], "details": None, "reason": "Nobody answered."}
VOICEMAIL = {**NO_ANSWER, "result": "voicemail", "reason": "Went to voicemail."}


@pytest.fixture
def world(monkeypatch):
    """Fake store + calendar; tests tweak `w` and read back what happened."""
    w = {
        "call": {
            "id": "call-1",
            "task_id": "task-1",
            "to_number": "+447700900123",
            "transcript": [{"speaker": "restaurant", "text": "Booked!"}],
            "status": "ended",
            "outcome": None,
            "business_name": "The Ivy Oxford",
        },
        "task": {
            "id": "task-1",
            "goal": "Book a table for 4 tomorrow at 6pm",
            "status": TaskStatus.CALLING,
            "agent_name": "Maya",
            "tools": ["phone", "calendar"],
            "user_name": "Demo User",
        },
        "saved_outcome": None,
        "finished": [],
        "calendar": [],
        "extract": BOOKED,
        "payments": [],
        "earlier": [],
    }

    async def load_call(call_id):
        return w["call"]

    async def load_task(task_id):
        return w["task"]

    async def task_payments(task_id):
        return w["payments"]

    async def earlier_calls(task_id, before_call_id):
        return w["earlier"]

    async def save_call_outcome(call_id, outcome):
        w["saved_outcome"] = outcome

    async def finish_task(task_id, status, summary):
        w["finished"].append((task_id, status, summary))

    async def extract_outcome(client, **kwargs):
        if isinstance(w["extract"], Exception):
            raise w["extract"]
        return w["extract"]

    async def add_event(event, task):
        w["calendar"].append(event)
        return "added"

    for fn in (load_call, load_task, save_call_outcome, finish_task, task_payments, earlier_calls):
        monkeypatch.setattr(store, fn.__name__, fn)
    monkeypatch.setattr(callbacks, "extract_outcome", extract_outcome)
    monkeypatch.setattr(declared.google_calendar, "add_event", add_event)
    return w


def gemini(monkeypatch, *responses):
    client = FakeClient(*responses)
    monkeypatch.setattr(callbacks, "get_client", lambda: client)
    return client


def test_booked_call_adds_calendar_event_and_finishes(monkeypatch, world):
    client = gemini(
        monkeypatch,
        model_says(
            call(
                "create_calendar_event",
                title="Dinner at The Ivy",
                starts_at="2026-10-25T18:00:00+00:00",
                ends_at="2026-10-25T19:30:00+00:00",
            )
        ),
        model_says(types.Part(text="Booked The Ivy for 4 at 18:00 and added it to your calendar.")),
    )

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert world["saved_outcome"] == BOOKED
    assert world["calendar"][0]["id"] == "task-1"  # bound by us, not chosen by Gemini
    assert world["finished"] == [
        ("task-1", TaskStatus.DONE, "Booked The Ivy for 4 at 18:00 and added it to your calendar.")
    ]
    prompt = client.requests[0][0].parts[0].text
    assert "The Ivy Oxford" in prompt and '"booked": true' in prompt


def test_phone_tools_are_not_offered_when_wrapping_up(monkeypatch, world):
    client = gemini(monkeypatch, model_says(types.Part(text="Done.")))
    declared_names = []
    original = callbacks.run_tool_loop

    async def spy(*args, tools, **kwargs):
        declared_names.extend(t.name for t in tools)
        return await original(*args, tools=tools, **kwargs)

    monkeypatch.setattr(callbacks, "run_tool_loop", spy)
    asyncio.run(callbacks.on_call_finished("call-1"))

    assert declared_names == ["create_calendar_event"]
    assert client.requests


def test_not_booked_marks_task_failed_and_reuses_stored_outcome(monkeypatch, world):
    world["call"]["outcome"] = FULL
    world["extract"] = AssertionError("should not re-extract")
    gemini(monkeypatch, model_says(types.Part(text="They're full at 18:00 but offered 20:30.")))

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert world["saved_outcome"] is None
    assert world["calendar"] == []
    assert world["finished"] == [("task-1", TaskStatus.FAILED, "They're full at 18:00 but offered 20:30.")]


def test_already_finished_task_is_skipped(monkeypatch, world):
    world["task"]["status"] = TaskStatus.DONE
    gemini(monkeypatch)

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert world["finished"] == []


def test_gemini_error_marks_task_failed(monkeypatch, world):
    world["extract"] = RuntimeError("429 quota")
    gemini(monkeypatch)

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert world["finished"] == [("task-1", TaskStatus.FAILED, callbacks.FAILED_SUMMARY)]


def test_calendar_times_get_correct_uk_offset():
    # UK clocks go back on 25 Oct 2026: 18:00 that day is GMT (+00:00), the day before is BST (+01:00).
    assert declared.uk_time("2026-10-25T18:00") == "2026-10-25T18:00:00+00:00"
    assert declared.uk_time("2026-10-24T18:00") == "2026-10-24T18:00:00+01:00"
    # A wrong offset from Gemini is replaced: the wall-clock time is what was agreed on the phone.
    assert declared.uk_time("2026-10-25T18:00:00+01:00") == "2026-10-25T18:00:00+00:00"


def test_calendar_tool_converts_times(monkeypatch, world):
    tool = declared.calendar_tools(world["task"])[0]
    asyncio.run(tool.handler(title="Dinner", starts_at="2026-10-25T18:00", ends_at="2026-10-25T19:30"))

    assert world["calendar"][0]["starts_at"] == "2026-10-25T18:00:00+00:00"
    assert world["calendar"][0]["ends_at"] == "2026-10-25T19:30:00+00:00"


def test_wrap_up_tells_gemini_the_payment_status(monkeypatch, world):
    world["payments"] = [{"amount": 2000, "merchant": "The Ivy Oxford", "status": "paid"}]
    client = gemini(monkeypatch, model_says(types.Part(text="Booked; £20 deposit paid.")))

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert "£20.00 to The Ivy Oxford: paid" in client.requests[0][0].parts[0].text



@pytest.fixture
def phone(monkeypatch):
    """A fake place_call under the phone permission; records the calls Gemini makes."""
    from app.orchestrator import runner
    from app.tools.base import Tool

    placed = []

    async def place_call(business_name, goal, **_):
        placed.append((business_name, goal))
        return {"status": "calling", "call_id": "call-2"}

    tool = Tool("place_call", "Call.", {"type": "object"}, place_call, ends_turn=True)
    monkeypatch.setitem(runner.TOOLS_BY_PERMISSION, "phone", lambda task: [tool])
    return placed


def offered(monkeypatch, world):
    """Records which tools Gemini was offered, then lets the real loop run."""
    names = []
    original = callbacks.run_tool_loop

    async def spy(*args, tools, **kwargs):
        names.extend(t.name for t in tools)
        return await original(*args, tools=tools, **kwargs)

    monkeypatch.setattr(callbacks, "run_tool_loop", spy)
    return names


def test_fully_booked_can_call_back_for_offered_time(monkeypatch, world, phone):
    world["task"]["goal"] = "Book The Ivy for 4 tomorrow at 6pm, or later if that's full"
    world["call"]["outcome"] = FULL
    client = gemini(monkeypatch, model_says(call("place_call", business_name="The Ivy Oxford", goal="Book 4 at 20:30")))

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert phone == [("The Ivy Oxford", "Book 4 at 20:30")]
    assert world["finished"] == []  # still calling; on_call_finished runs again when call 2 ends
    assert 'business_name "The Ivy Oxford"' in client.requests[0][0].parts[0].text


@pytest.mark.parametrize("outcome", [NO_ANSWER, FULL])
def test_no_second_retry_after_two_calls(monkeypatch, world, phone, outcome):
    world["call"]["outcome"] = outcome
    world["earlier"] = [{"status": "no_answer", "outcome": NO_ANSWER}]
    names = offered(monkeypatch, world)
    client = gemini(monkeypatch, model_says(types.Part(text="Tried twice, nobody could book it.")))

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert "place_call" not in names
    assert world["finished"] == [("task-1", TaskStatus.FAILED, "Tried twice, nobody could book it.")]
    prompt = client.requests[0][0].parts[0].text
    assert "Earlier calls for this task: Nobody answered." in prompt
    assert "You can't make another call" in prompt


@pytest.mark.parametrize("outcome", [VOICEMAIL, BOOKED])
def test_no_call_back_after_voicemail_or_booking(monkeypatch, world, phone, outcome):
    world["call"]["outcome"] = outcome
    names = offered(monkeypatch, world)
    gemini(monkeypatch, model_says(types.Part(text="Summary.")))

    asyncio.run(callbacks.on_call_finished("call-1"))

    assert "place_call" not in names
    assert phone == []


def test_calendar_tool_says_when_google_calendar_is_not_connected(monkeypatch, world):
    async def not_connected(event, task):
        return "not_connected"

    monkeypatch.setattr(declared.google_calendar, "add_event", not_connected)
    tool = declared.calendar_tools(world["task"])[0]
    result = asyncio.run(tool.handler(title="Dinner", starts_at="2026-10-25T18:00", ends_at="2026-10-25T19:30"))

    assert "isn't connected" in result["error"]
