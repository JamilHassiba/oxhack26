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
from app.tools.phone import MAX_CALLS_PER_TASK

log = logging.getLogger(__name__)

FAILED_SUMMARY = "The call has ended, but something went wrong while finishing the task. Please check the call details."
# Worth one more call: an offered time that fits what the user asked for, or nobody picked up.
# Voicemail and a plain "no" are not: calling straight back would just annoy the business.
RETRYABLE = {"fully_booked", "no_answer"}


async def on_call_finished(call_id: str) -> None:
    """Called by Jamil's post-call webhook after the transcript and outcome are saved on the calls row.

    Works out the outcome (booked? time? deposit?), lets Gemini add the calendar event and send the
    confirmation email, then saves the summary and marks the task done (or failed if nothing was booked).
    If it wasn't booked and one more call makes sense (another time offered, or no answer), Gemini may
    call again (max MAX_CALLS_PER_TASK per task); this function then runs again when that call ends.
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
            outcome = await extract_outcome(
                client, model=model, goal=task["goal"], transcript=call["transcript"], call_status=call["status"]
            )
            await store.save_call_outcome(call_id, outcome)

        payments = await store.task_payments(task["id"])
        earlier = await store.earlier_calls(task["id"], call_id)
        can_call_again = (
            not outcome.get("booked")
            and outcome.get("result") in RETRYABLE
            and call["business_name"] is not None
            and len(earlier) + 1 < MAX_CALLS_PER_TASK
        )
        # place_call only when a second call is allowed.
        tools = [t for t in tools_for(task) if t.name != "place_call" or can_call_again]
        message = wrap_up_message(task, call, outcome, payments, earlier, can_call_again)
        result = await run_tool_loop(
            client,
            model=model,
            system_instruction=build_system_prompt(
                agent_name=task["agent_name"],
                user_name=task["user_name"],
                tool_names=[t.name for t in tools],
            ),
            contents=[types.Content(role="user", parts=[types.Part(text=message)])],
            tools=tools,
        )
    except Exception:
        log.exception("on_call_finished(%s) failed", call_id)
        await store.finish_task(task["id"], TaskStatus.FAILED, FAILED_SUMMARY)
        return

    if result.paused_on == "place_call":
        log.info("on_call_finished(%s): calling again (%s)", call_id, outcome.get("result"))
        return
    status = TaskStatus.DONE if outcome.get("booked") else TaskStatus.FAILED
    await store.finish_task(task["id"], status, result.text.strip() or outcome.get("reason") or "The call has ended.")


def wrap_up_message(
    task: dict[str, Any],
    call: dict[str, Any],
    outcome: dict[str, Any],
    payments: list[dict[str, Any]],
    earlier: list[dict[str, Any]],
    can_call_again: bool,
) -> str:
    who = call["business_name"] or "the business"
    paid = [f"£{p['amount'] / 100:.2f} to {p['merchant'] or who}: {p['status']}" for p in payments]
    before = [(c["outcome"] or {}).get("reason") or c["status"] for c in earlier]
    if can_call_again:
        next_call = f"""- It wasn't booked, and you may call {who} once more (place_call with business_name "{who}"):
  - If they offered another time that fits what the user asked for (for example the user gave a range, said "or later", or listed alternatives), call again to book exactly that time: put the offered time in the goal, e.g. "Book a table for 4 tomorrow at 20:30". If the user only gave one time, don't call: tell them which time was offered.
  - If nobody answered, call once more with the same goal.
  - Otherwise don't call again.
  If you call, stop after place_call: you'll get its result later."""
    else:
        next_call = "- You can't make another call for this task."
    return f"""Your task: {task["goal"]}

You phoned {who} and the call has ended.
Earlier calls for this task: {"; ".join(before) or "none"}
Result of this call: {json.dumps(outcome)}
Payments for this task (amount: status): {"; ".join(paid) or "none"}
Call transcript:
{transcript_text(call["transcript"])}

Finish the task now:
- If it was booked: add it to the calendar and email the user a confirmation, if you have those tools. If no end time was given, a meal lasts about 1.5 hours.
- Deposits: only say one was paid if its status above is "paid". If it is "denied", say the user declined it. If a deposit is needed and there is no paid payment, say it still has to be paid.
{next_call}
- If it wasn't booked and you don't call again: don't add anything. Explain what happened (no answer, voicemail, fully booked...) and what the user can do next, including any other times that were offered.
Then write the summary for the user."""
