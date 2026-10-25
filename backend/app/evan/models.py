"""HTTP models matching frontend/src/types.ts. Kept out of the shared schemas file."""

from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

Tool = Literal["phone", "email", "calendar", "payments"]
TaskStatus = Literal["planning", "calling", "awaiting_approval", "done", "failed"]
Name = Annotated[str, Field(min_length=1, max_length=40)]


class AgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name
    tools: list[Tool]

    @field_validator("tools")
    @classmethod
    def unique_tools(cls, value):
        return list(dict.fromkeys(value))


class AgentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name | None = None
    tools: list[Tool] | None = None

    @model_validator(mode="after")
    def no_null_or_empty_patch(self):
        if not self.model_fields_set or any(
            getattr(self, name) is None for name in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null agent field.")
        if self.tools is not None:
            self.tools = list(dict.fromkeys(self.tools))
        return self


class Agent(AgentInput):
    # Row metadata never crosses this response boundary.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    id: str


class TranscriptLine(BaseModel):
    speaker: str
    text: str


class CallOutcome(BaseModel):
    """What Gemini extracted from the call (orchestrator/outcome.py); drives the booking summary table.
    Every field is optional: older calls were extracted before some fields existed."""

    result: str | None = None  # booked | fully_booked | no_answer | voicemail | declined | other
    booked: bool | None = None
    starts_at: str | None = None  # UK wall-clock time, e.g. "2026-10-26T18:30" (no offset)
    details: str | None = None
    booking_name: str | None = None
    venue: str | None = None
    deposit_required: bool | None = None
    deposit_amount_pence: int | None = None
    offered_times: list[str] = Field(default_factory=list)
    reason: str | None = None


class Call(BaseModel):
    id: str
    status: str
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    transcript: list[TranscriptLine] = Field(default_factory=list)
    outcome: CallOutcome | None = None


class Payment(BaseModel):
    id: str
    task_id: str
    amount: int = Field(ge=0)
    currency: str
    merchant: str | None = None
    status: Literal["pending_approval", "approved", "paid", "denied"]


class EventPayload(BaseModel):
    speaker: str | None = None
    text: str | None = None


class CallEvent(BaseModel):
    ts: AwareDatetime
    call_id: str
    kind: Literal[
        "dialing",
        "ringing",
        "answered",
        "transcript_line",
        "tool_call",
        "payment",
        "ended",
    ]
    payload: EventPayload = Field(default_factory=EventPayload)


class Task(BaseModel):
    id: str
    agent_id: str
    goal: str
    status: TaskStatus
    summary: str | None = None
    created_at: AwareDatetime
    call: Call | None = None
    payment: Payment | None = None
    events: list[CallEvent] = Field(default_factory=list)

