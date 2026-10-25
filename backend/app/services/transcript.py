"""Turns ElevenLabs transcript turns into our lines.

Used by the post-call webhook (routers/webhooks.py). ElevenLabs only gives an agent call's transcript
once the call has ended, so there is no live transcript.
"""

import re
from dataclasses import dataclass
from typing import Any

# The voice agent's emotion cues, e.g. "[warmly] ", which aren't meant to be read.
EMOTION_TAG = re.compile(r"\[[a-zA-Z ]+\]\s*")


@dataclass
class Line:
    role: str  # "agent" or "user" (the business)
    text: str
    seconds: float  # into the call


def transcript_lines(turns: list[dict[str, Any]]) -> list[Line]:
    """Non-empty lines in order; the agent's emotion tags removed."""
    lines = []
    for turn in turns:
        text = turn.get("message") or ""
        if turn.get("role") == "agent":
            text = EMOTION_TAG.sub("", text)
        if text.strip():
            lines.append(Line(turn.get("role") or "user", text.strip(), float(turn.get("time_in_call_secs") or 0)))
    return lines
