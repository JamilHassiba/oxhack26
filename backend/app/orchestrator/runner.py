"""run_task: runs Gemini for one task in the background and saves the result."""

import logging
from collections.abc import Callable
from typing import Any

from google.genai import types

from app.config import get_settings
from app.contracts import TaskStatus
from app.orchestrator import store
from app.orchestrator.loop import run_tool_loop
from app.orchestrator.prompts import build_system_prompt
from app.services.gemini import get_client
from app.tools.base import Tool
from app.tools.declared import calendar_tools, email_tools
from app.tools.phone import phone_tools

log = logging.getLogger(__name__)

# Agent permission -> builds the tools Gemini may call with it, bound to one task. Payments come later.
TOOLS_BY_PERMISSION: dict[str, Callable[[dict[str, Any]], list[Tool]]] = {
    "phone": phone_tools,
    "calendar": calendar_tools,
    "email": email_tools,
}

FAILED_SUMMARY = "Sorry, something went wrong while working on this. Please try again."
MAX_SUMMARY_CHARS = 1500


def history_contents(previous: list[dict[str, Any]]) -> list[types.Content]:
    """Earlier tasks as earlier chat turns (user asked -> agent replied), so follow-ups like
    "OK, book the 8:30 one" make sense. The chat box is locked during a task, so each task is one exchange."""
    contents = []
    for task in previous:
        reply = task["summary"][:MAX_SUMMARY_CHARS]
        if task["status"] == TaskStatus.FAILED:
            reply = f"(This task did not succeed.) {reply}"
        contents.append(types.Content(role="user", parts=[types.Part(text=task["goal"])]))
        contents.append(types.Content(role="model", parts=[types.Part(text=reply)]))
    return contents


def tools_for(task: dict[str, Any]) -> list[Tool]:
    """Only the tools the agent is allowed to use are declared to Gemini."""
    return [tool for permission in task["tools"] if permission in TOOLS_BY_PERMISSION
            for tool in TOOLS_BY_PERMISSION[permission](task)]


async def run_task(task_id: str) -> None:
    try:
        task = await store.load_task(task_id)
        previous = await store.recent_tasks(task["agent_id"], task_id)
        tools = tools_for(task)
        result = await run_tool_loop(
            get_client(),
            model=get_settings().gemini_model,
            system_instruction=build_system_prompt(
                agent_name=task["agent_name"],
                persona=task["persona"],
                user_name=task["user_name"],
                tool_names=[t.name for t in tools],
                phone_allowed="phone" in task["tools"],
            ),
            contents=[*history_contents(previous), types.Content(role="user", parts=[types.Part(text=task["goal"])])],
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
