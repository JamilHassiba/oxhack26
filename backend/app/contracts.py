"""Shared contract between Jamil (voice/infra) and Alex (orchestrator). Change only after telling the team.

Call flow:
    Alex: place_call tool --await start_call(brief)--> Jamil: calls row + ElevenLabs call -> call_id
    Jamil: post-call webhook stores transcript/outcome on calls --await on_call_finished(call_id)--> Alex: resume Gemini

    Jamil implements  app.services.elevenlabs.start_call(brief: CallBrief) -> str   (async, returns call_id)
    Alex implements   app.orchestrator.callbacks.on_call_finished(call_id: str) -> None   (async)

All IDs are strings (DB columns are Postgres uuid, converted to str when read).

call_events kinds/payloads: owned by Jamil, documented in docs/EVENTS.md.
"""

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class CallBrief:
    """What the voice agent needs for one call. Built by the orchestrator from the user's request."""

    task_id: str  # so start_call can create the calls row linked to the task
    to_number: str  # E.164, e.g. "+447700900123": always CALL_NUMBER
    goal: str  # "Book a table for 4 at Dishoom tonight at 18:00"
    user_name: str  # "I'm an AI assistant calling on behalf of <user_name>"
    agent_name: str
    constraints: list[str] = field(default_factory=list)  # ["party of 4", "deposit up to £20 is fine"]
    fallbacks: list[str] = field(default_factory=list)  # ["17:30", "18:30"] if the goal time is unavailable
    business_name: str = ""  # "Dishoom", as the user named it; saved on the call for labels and summaries


class TaskStatus(StrEnum):
    PLANNING = "planning"
    CALLING = "calling"
    AWAITING_APPROVAL = "awaiting_approval"
    DONE = "done"
    FAILED = "failed"


class PaymentStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"  # created by Jamil's request_payment_approval server tool
    APPROVED = "approved"  # user clicked Approve (Alex's endpoint)
    PAID = "paid"  # Stripe test-mode charge succeeded
    DENIED = "denied"  # user clicked Deny
