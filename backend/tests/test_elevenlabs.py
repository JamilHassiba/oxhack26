import asyncio
from dataclasses import replace

from app.config import Settings
from app.contracts import CallBrief
from app.services import elevenlabs

BRIEF = CallBrief(
    task_id="task-1",
    to_number="+447700900123",
    goal="Book a table for 4 tomorrow at 18:00",
    user_name="Jamil",
    agent_name="Maya",
    constraints=["party of 4", "name Jamil"],
    fallbacks=["17:30", "18:30"],
)


def test_dynamic_variables_fill_the_agent_prompt():
    variables = elevenlabs.dynamic_variables(BRIEF, "call-1")
    assert variables == {
        "agent_name": "Maya",
        "user_name": "Jamil",
        "goal": "book a table for 4 tomorrow at 18:00",
        "constraints": "party of 4, name Jamil",
        "fallbacks": "17:30, 18:30",
        "call_id": "call-1",
    }



def test_goal_drops_its_full_stop():
    # The first message already ends the sentence: "I'm calling to {{goal}}."
    brief = replace(BRIEF, goal="Book a haircut tomorrow at 5pm.")
    assert elevenlabs.dynamic_variables(brief, "c")["goal"] == "book a haircut tomorrow at 5pm"


def test_empty_lists_read_as_none():
    brief = CallBrief(task_id="t", to_number="+44", goal="Ask", user_name="J", agent_name="M")
    variables = elevenlabs.dynamic_variables(brief, "c")
    assert variables["constraints"] == "none" and variables["fallbacks"] == "none"


def test_without_api_key_falls_back_to_practice_run(monkeypatch):
    monkeypatch.setattr(elevenlabs, "get_settings", lambda: Settings(elevenlabs_api_key=""))
    seen = []

    async def stand_in(brief):
        seen.append(brief)
        return "practice-call"

    monkeypatch.setattr("app.tools.phone.stand_in_start_call", stand_in)
    assert asyncio.run(elevenlabs.start_call(BRIEF)) == "practice-call"
    assert seen == [BRIEF]
