"""Entry points other components call into the orchestrator."""

import logging

log = logging.getLogger(__name__)


async def on_call_finished(call_id: str) -> None:
    """Called by Jamil's post-call webhook after the transcript and outcome are saved on the calls row.

    Phase 1: load the calls row and its task, append the outcome to the saved Gemini history,
    resume the tool loop (calendar, email, payment, summary) and save tasks.summary.
    """
    log.warning("on_call_finished(%s): not implemented yet (Phase 1)", call_id)
