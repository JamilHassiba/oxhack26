from app.contracts import CallBrief, PaymentStatus, TaskStatus


def test_statuses_match_design_doc():
    assert [s.value for s in TaskStatus] == ["planning", "calling", "awaiting_approval", "done", "failed"]
    assert [s.value for s in PaymentStatus] == ["pending_approval", "approved", "paid", "denied"]


def test_brief_defaults():
    brief = CallBrief(task_id="t1", to_number="+447700900123", goal="Book a table", user_name="Alex", agent_name="Maya")
    assert brief.constraints == [] and brief.fallbacks == []

