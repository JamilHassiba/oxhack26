"""run_task: runs Gemini for one task in the background and saves the result."""

import logging

from google.genai import types

from app.config import get_settings
from app.contracts import TaskStatus
from app.orchestrator import store
from app.orchestrator.loop import run_tool_loop
from app.orchestrator.prompts import build_system_prompt
from app.services.gemini import get_client
from app.tools.base import Tool

log = logging.getLogger(__name__)

# Agent permission -> tools Gemini may call with it. Later steps fill this in
# (phone: lookup_contact + place_call, calendar, email, payments).
TOOLS_BY_PERMISSION: dict[str, list[Tool]] = {}

FAILED_SUMMARY = "Sorry, something went wrong while working on this. Please try again."


def tools_for(permissions: list[str]) -> list[Tool]:
    """Only the tools the agent is allowed to use are declared to Gemini."""
    return [tool for permission in permissions for tool in TOOLS_BY_PERMISSION.get(permission, [])]


async def run_task(task_id: str) -> None:
    try:
        task = await store.load_task(task_id)
        tools = tools_for(task["tools"])
        result = await run_tool_loop(
            get_client(),
            model=get_settings().gemini_model,
            system_instruction=build_system_prompt(
                agent_name=task["agent_name"],
                persona=task["persona"],
                user_name=task["user_name"],
                tool_names=[t.name for t in tools],
            ),
            contents=[types.Content(role="user", parts=[types.Part(text=task["goal"])])],
            tools=tools,
        )
    except Exception:
        log.exception("Task %s failed", task_id)
        await store.finish_task(task_id, TaskStatus.FAILED, FAILED_SUMMARY)
        return

    if result.paused_on:
        # A tool like place_call paused the loop and set the status; on_call_finished resumes it.
        return
    await store.finish_task(task_id, TaskStatus.DONE, result.text.strip() or "Done.")
