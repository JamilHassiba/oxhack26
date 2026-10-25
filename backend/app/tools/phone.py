"""`place_call` tool: wraps Jamil's start_call. Owner: Alex.

Every call rings the one configured CALL_NUMBER (the person playing the business in the demo), whatever
business the user names. Gemini only passes the business's name, which is saved on the call so the
transcript, summary and calendar use it. Gemini never chooses a phone number.
"""

import logging
from typing import Any

from psycopg.types.json import Jsonb

from app import db
from app.config import get_settings
from app.contracts import CallBrief, TaskStatus
from app.orchestrator import store
from app.tools.base import Tool

try:
    from app.services.elevenlabs import start_call
except ImportError:  # Jamil's real start_call isn't on main yet; use the stand-in below.
    start_call = None

log = logging.getLogger(__name__)

MAX_CALLS_PER_TASK = 2


async def stand_in_start_call(brief: CallBrief) -> str:
    """Stand-in for Jamil's start_call: records the call and its `dialing` event (docs/EVENTS.md), dials nobody."""
    log.warning("start_call stand-in: no real phone call is made (task %s)", brief.task_id)
    async with db.get_pool().connection() as conn, conn.transaction():
        (call_id,) = await (
            await conn.execute(
                "INSERT INTO calls (task_id, to_number, business_name) VALUES (%s, %s, %s) RETURNING id",
                (brief.task_id, brief.to_number, brief.business_name or None),
            )
        ).fetchone()
        await conn.execute(
            "INSERT INTO call_events (ts, call_id, kind, payload) VALUES (clock_timestamp(), %s, 'dialing', %s)",
            (
                call_id,
                # Extra fields are allowed (EVENTS.md rule 4); fake_call_end uses `goal` for its transcript.
                Jsonb({"text": "Calling (practice run: no real phone call)", "to_number": brief.to_number, "goal": brief.goal}),
            ),
        )
    return str(call_id)


def phone_tools(task: dict[str, Any]) -> list[Tool]:
    """Tools for one task: task_id, user and agent are bound here, never chosen by Gemini."""

    async def place_call(
        business_name: str, goal: str, constraints: list[str] | None = None, fallbacks: list[str] | None = None
    ) -> dict:
        number = get_settings().call_number
        if not number:
            return {"error": "No phone number is configured (CALL_NUMBER), so calls are switched off."}
        if not business_name.strip():
            return {"error": "Give the name of the business to call."}
        if await store.count_calls(task["id"]) >= MAX_CALLS_PER_TASK:
            return {"error": f"This task has already made {MAX_CALLS_PER_TASK} calls. No more calls are allowed."}

        brief = CallBrief(
            task_id=task["id"],
            to_number=number,
            goal=goal,
            user_name=task["user_name"],
            agent_name=task["agent_name"],
            constraints=list(constraints or []),
            fallbacks=list(fallbacks or []),
            business_name=business_name.strip(),
        )
        call_id = await (start_call or stand_in_start_call)(brief)
        await store.set_task_status(task["id"], TaskStatus.CALLING)
        return {"status": "calling", "call_id": call_id, "business": brief.business_name}

    return [
        Tool(
            name="place_call",
            description=(
                "Phone a business. A voice agent makes the call; you get the result later, so stop after calling this."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "business_name": {
                        "type": "string",
                        "description": "The business to call.",
                    },
                    "goal": {
                        "type": "string",
                        "description": (
                            "What the call should achieve, with days and times as the user said them (never the year), "
                            "e.g. 'book a table for 2 tomorrow at 7pm'."
                        ),
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Anything the voice agent should know.",
                    },
                    "fallbacks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternatives the user said are fine.",
                    },
                },
                "required": ["business_name", "goal"],
            },
            handler=place_call,
            ends_turn=True,
        ),
    ]
