"""Entry points other components call into the orchestrator."""

import json
import logging
from typing import Any

from google.genai import types

from app.config import get_settings
from app.contracts import TaskStatus
from app.orchestrator import store
from app.orchestrator.loop import run_tool_loop
from app.orchestrator.outcome import extract_outcome, transcript_text
from app.orchestrator.prompts import build_system_prompt
from app.orchestrator.runner import tools_for
from app.services.gemini import get_client

log = logging.getLogger(__name__)

# No new calls while wrapping up (retrying with a fallback time is a later step).
PHONE_TOOLS = {"lookup_contact", "place_call"}
FAILED_SUMMARY = "The call has ended, but something went wrong while finishing the task. Please check the call details."


async def on_call_finished(call_id: str) -> None:
    """Called by Jamil's post-call webhook after the transcript and outcome are saved on the calls row.

    Works out the outcome (booked? time? deposit?), lets Gemini add the calendar event and send the
    confirmation email, then saves the summary and marks the task done (or failed if nothing was booked).
    """
    call = await store.load_call(call_id)
    task = await store.load_task(call["task_id"])
    if task["status"] not in (TaskStatus.CALLING, TaskStatus.AWAITING_APPROVAL):
        log.warning("on_call_finished(%s): task %s is already %s, skipping", call_id, task["id"], task["status"])
        return

    try:
        client, model = get_client(), get_settings().gemini_model
        outcome = call["outcome"]
        if not outcome:
            outcome = await extract_outcome(client, model=model, goal=task["goal"], transcript=call["transcript"])
            await store.save_call_outcome(call_id, outcome)

        tools = [t for t in tools_for(task) if t.name not in PHONE_TOOLS]
        result = await run_tool_loop(
            client,
            model=model,
            system_instruction=build_system_prompt(
                agent_name=task["agent_name"],
                persona=task["persona"],
                user_name=task["user_name"],
                tool_names=[t.name for t in tools],
            ),
            contents=[types.Content(role="user", parts=[types.Part(text=wrap_up_message(task, call, outcome))])],
            tools=tools,
        )
    except Exception:
        log.exception("on_call_finished(%s) failed", call_id)
        await store.finish_task(task["id"], TaskStatus.FAILED, FAILED_SUMMARY)
        return

    status = TaskStatus.DONE if outcome.get("booked") else TaskStatus.FAILED
    await store.finish_task(task["id"], status, result.text.strip() or outcome.get("reason") or "The call has ended.")


def wrap_up_message(task: dict[str, Any], call: dict[str, Any], outcome: dict[str, Any]) -> str:
    who = call["contact_name"] or "the business"
    return f"""Your task: {task["goal"]}

You phoned {who} and the call has ended.
Result of the call: {json.dumps(outcome)}
Call transcript:
{transcript_text(call["transcript"])}

Finish the task now:
- If it was booked: add it to the calendar and email the user a confirmation, if you have those tools. If no end time was given, a meal lasts about 1.5 hours.
- A deposit is never paid during the call (payment happens separately). If one is needed, say it still has to be paid; never say it has been paid.
- If it wasn't booked: don't add anything. Explain what happened and what the user can do next (for example another time that was offered).
Then write the summary for the user."""
