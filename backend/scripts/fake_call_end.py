"""Stand-in for Jamil's post-call webhook, for testing without a real phone call. Owner: Alex.

Writes a made-up transcript onto a call and its call events (answered, transcript lines, ended, in the
docs/EVENTS.md format, so the website's timeline shows them), then runs on_call_finished(call_id).

    cd backend
    .venv/Scripts/python -m scripts.fake_call_end <call_id> booked      # table confirmed, £20 deposit
    .venv/Scripts/python -m scripts.fake_call_end <call_id> full        # fully booked, 20:30 offered
    .venv/Scripts/python -m scripts.fake_call_end <call_id> no_answer   # nobody picked up
    .venv/Scripts/python -m scripts.fake_call_end <call_id> voicemail   # answering machine
"""

import argparse
import asyncio
import logging

from psycopg.types.json import Jsonb

from app import db
from app.config import get_settings
from app.orchestrator.callbacks import on_call_finished

SCENARIOS = {
    "booked": [
        ("restaurant", "Good evening, {contact}, how can I help?"),
        ("agent", "Hi, I'm an AI assistant calling on behalf of {user}. I'd like to book a table: {goal}"),
        ("restaurant", "Let me check... yes, we can do that. We take a £20 deposit for groups. What name is it under?"),
        ("agent", "{user}, please. The deposit is fine."),
        ("restaurant", "Lovely, that's booked under {user}. See you then!"),
        ("agent", "Thank you, goodbye."),
    ],
    "full": [
        ("restaurant", "{contact}, good evening."),
        ("agent", "Hi, I'm an AI assistant calling on behalf of {user}. I'd like to book a table: {goal}"),
        ("restaurant", "I'm sorry, we're fully booked then. The earliest we could do is 8:30pm."),
        ("agent", "Thanks, I'll check with {user} and call back if that works. Goodbye."),
    ],
    "no_answer": [],
    "voicemail": [
        ("restaurant", "Hi, you've reached {contact}. We can't take your call right now, please leave a message."),
    ],
}

# How each scenario ends, as in EVENTS.md: (ended reason, timeline text, calls.status)
ENDINGS = {
    "booked": ("completed", "Call finished", "ended"),
    "full": ("completed", "Call finished", "ended"),
    "no_answer": ("no_answer", "No answer", "no_answer"),
    "voicemail": ("voicemail", "Went to voicemail", "voicemail"),
}


async def main(call_id: str, scenario: str) -> None:
    await db.open_pool(get_settings().database_url)
    try:
        async with db.get_pool().connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT COALESCE(
                               (SELECT payload->>'goal' FROM call_events
                                WHERE call_id = c.id AND kind = 'dialing' ORDER BY ts LIMIT 1),
                               t.goal),
                           u.name, a.name,
                           c.business_name
                    FROM calls c JOIN tasks t ON t.id = c.task_id
                    JOIN agents a ON a.id = t.agent_id JOIN users u ON u.id = a.user_id
                    WHERE c.id = %s
                    """,
                    (call_id,),
                )
            ).fetchone()
            if row is None:
                raise SystemExit(f"No call with id {call_id}")
            goal, user, agent, contact = row
            contact = contact or "Restaurant"
            # EVENTS.md: speaker is the agent's name for the AI, the contact's name for the other person.
            speakers = {"agent": agent, "restaurant": contact}
            transcript = [
                {"speaker": speakers[role], "text": text.format(goal=goal, user=user, contact=contact)}
                for role, text in SCENARIOS[scenario]
            ]
            reason, ended_text, call_status = ENDINGS[scenario]
            events = [{"kind": "answered", "text": "Connected"}] if reason == "completed" else []
            events += [{"kind": "transcript_line", **line} for line in transcript]
            events.append(
                {"kind": "ended", "text": ended_text, "reason": reason, "duration_seconds": 8 * len(transcript)}
            )
            async with conn.transaction():
                await conn.execute(
                    "UPDATE calls SET transcript = %s, status = %s, ended_at = now() WHERE id = %s",
                    (Jsonb(transcript), call_status, call_id),
                )
                for event in events:
                    kind = event.pop("kind")
                    await conn.execute(
                        "INSERT INTO call_events (ts, call_id, kind, payload) VALUES (clock_timestamp(), %s, %s, %s)",
                        (call_id, kind, Jsonb(event)),
                    )
        print(f"Saved a fake '{scenario}' transcript on call {call_id}; running on_call_finished...")
        await on_call_finished(call_id)
        print("Done. Check the task in the app (or GET /tasks/{task_id}).")
    finally:
        await db.close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("call_id")
    parser.add_argument("scenario", choices=SCENARIOS)
    args = parser.parse_args()
    # Selector loop: psycopg's async mode can't use Windows' default loop.
    asyncio.run(main(args.call_id, args.scenario), loop_factory=asyncio.SelectorEventLoop)
