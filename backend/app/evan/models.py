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
Persona = Annotated[str, Field(min_length=1, max_length=1500)]


class AgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name
    persona: Persona
    voice: str = Field(min_length=1, max_length=100)
    tools: list[Tool]

    @field_validator("tools")
    @classmethod
    def unique_tools(cls, value):
        return list(dict.fromkeys(value))


class AgentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name | None = None
    persona: Persona | None = None
    voice: str | None = Field(default=None, min_length=1, max_length=100)
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


class Call(BaseModel):
    id: str
    status: str
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    transcript: list[TranscriptLine] = Field(default_factory=list)


class Payment(BaseModel):
    id: str
    task_id: str
    amount: int = Field(ge=0)
    currency: str
    merchant: str | None = None
    status: Literal["pending_approval", "approved", "paid", "denied"]


class CalendarEvent(BaseModel):
    id: str
    task_id: str
    title: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    location: str


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
    calendar_event: CalendarEvent | None = None
    events: list[CallEvent] = Field(default_factory=list)


class CalendarInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    location: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def positive_duration(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("The event must end after it starts.")
        return self
