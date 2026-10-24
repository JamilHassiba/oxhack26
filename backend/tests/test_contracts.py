import asyncio

from app.contracts import CallBrief, PaymentStatus, TaskStatus
from app.orchestrator.callbacks import on_call_finished


def test_statuses_match_design_doc():
    assert [s.value for s in TaskStatus] == ["planning", "calling", "awaiting_approval", "done", "failed"]
    assert [s.value for s in PaymentStatus] == ["pending_approval", "approved", "paid", "denied"]


def test_brief_defaults():
    brief = CallBrief(task_id="t1", to_number="+447700900123", goal="Book a table", user_name="Alex", agent_name="Maya")
    assert brief.constraints == [] and brief.fallbacks == []


def test_on_call_finished_stub_is_awaitable():
    assert asyncio.run(on_call_finished("call-1")) is None
