"""`place_call` tool: wraps Jamil's start_call. Owner: Alex.

Also `lookup_contact`, so Gemini can find who to call. Gemini only ever sees contact ids, never phone
numbers: place_call looks the number up itself, so the model can't dial a number it made up.
"""

import logging
from typing import Any

from psycopg.types.json import Jsonb

from app import db
from app.contracts import CallBrief, TaskStatus
from app.orchestrator import store
from app.services import live_transcript
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
                "INSERT INTO calls (task_id, to_number) VALUES (%s, %s) RETURNING id", (brief.task_id, brief.to_number)
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

    async def lookup_contact(name: str) -> dict:
        matches = await store.find_contacts(name)
        if matches:
            return {"found": True, "contacts": matches}
        return {"found": False, "known_contacts": await store.list_contact_names()}

    async def place_call(
        contact_id: str, goal: str, constraints: list[str] | None = None, fallbacks: list[str] | None = None
    ) -> dict:
        contact = await store.get_contact(contact_id)
        if contact is None:
            return {"error": "Unknown contact_id. Use lookup_contact first and pass its contact_id."}
        if await store.count_calls(task["id"]) >= MAX_CALLS_PER_TASK:
            return {"error": f"This task has already made {MAX_CALLS_PER_TASK} calls. No more calls are allowed."}

        brief = CallBrief(
            task_id=task["id"],
            to_number=contact["phone"],
            goal=goal,
            user_name=task["user_name"],
            agent_name=task["agent_name"],
            constraints=list(constraints or []),
            fallbacks=list(fallbacks or []),
        )
        call_id = await (start_call or stand_in_start_call)(brief)
        await store.set_task_status(task["id"], TaskStatus.CALLING)
        live_transcript.start(call_id)  # real calls only: shows the conversation while it happens
        return {"status": "calling", "call_id": call_id, "contact": contact["name"]}

    return [
        Tool(
            name="lookup_contact",
            description="Find a business to call by name (e.g. a restaurant). Returns matching contacts with their contact_id.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Business name or part of it, e.g. 'Ivy'."}},
                "required": ["name"],
            },
            handler=lookup_contact,
        ),
        Tool(
            name="place_call",
            description=(
                "Phone a contact. A voice agent makes the call in the background; you get the result later, "
                "so stop after calling this."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "contact_id from lookup_contact."},
                    "goal": {
                        "type": "string",
                        "description": "What the call must achieve, e.g. 'Book a table for 4 tomorrow at 18:00'.",
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Details and limits, e.g. ['party of 4', 'deposit up to £20 is fine'].",
                    },
                    "fallbacks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Acceptable alternatives if the goal isn't possible, e.g. ['17:30', '18:30'].",
                    },
                },
                "required": ["contact_id", "goal"],
            },
            handler=place_call,
            ends_turn=True,
        ),
    ]
