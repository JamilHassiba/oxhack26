"""Structured outcome extraction: reads a call transcript and returns the facts as JSON (Gemini structured output)."""

import json
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types

OUTCOME_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {
            "type": "string",
            "enum": ["booked", "fully_booked", "no_answer", "voicemail", "declined", "other"],
            "description": "What happened. fully_booked: no space at the asked time. declined: they said no for another reason.",
        },
        "booked": {
            "type": "boolean",
            "description": "True only if the business clearly confirmed the booking or request.",
        },
        "starts_at": {
            "type": ["string", "null"],
            "description": "Confirmed UK local date and time, e.g. 2026-10-25T18:00. Null if nothing was confirmed.",
        },
        "party_size": {"type": ["integer", "null"]},
        "booking_name": {
            "type": ["string", "null"],
            "description": "The name the booking is under, as said on the call. Null if none was given.",
        },
        "venue": {"type": ["string", "null"], "description": "The business that was called, e.g. 'The Ivy Oxford'."},
        "deposit_required": {"type": "boolean"},
        "deposit_amount_pence": {
            "type": ["integer", "null"],
            "description": "Deposit in whole pence, e.g. 2000 for £20. Null if no deposit.",
        },
        "offered_times": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Other times the business offered, as UK local date and time, e.g. 2026-10-25T20:30.",
        },
        "reason": {
            "type": "string",
            "description": "One short sentence on what happened, e.g. 'Fully booked at 18:00; 20:30 offered'.",
        },
    },
    "required": [
        "result", "booked", "starts_at", "party_size", "booking_name", "venue", "deposit_required",
        "deposit_amount_pence", "offered_times", "reason",
    ],
}


def transcript_text(transcript: list[dict[str, Any]]) -> str:
    return "\n".join(f"{line.get('speaker', '?')}: {line.get('text', '')}" for line in transcript) or (
        "(no conversation: nobody answered)"
    )


async def extract_outcome(
    client: genai.Client,
    *,
    model: str,
    goal: str,
    transcript: list[dict[str, Any]],
    call_status: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    prompt = (
        "Extract the result of this phone call as JSON.\n"
        f"Goal of the call: {goal}\n"
        f"Call status from the phone system: {call_status or 'unknown'}\n"
        f"Today is {now:%A %d %B %Y} (UTC). Times said on the call are UK local time (Europe/London).\n\n"
        f"Transcript:\n{transcript_text(transcript)}"
    )
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=OUTCOME_SCHEMA,
        ),
    )
    return json.loads(response.text)
