# Gemini API: submission notes

Owner: Alex. Ready-to-paste bullets for the Devpost/MLH page and the Gemini sponsor challenge, plus the evidence behind them.

## Short version (paste into the submission)

**How we use the Gemini API**

- **Gemini is the brain of every agent.** You chat with an agent ("Book a table for 4 at The Ivy tomorrow at 6pm, or later if it's full"); Gemini plans the task and calls our tools through **function calling**: look up the business, place a real phone call, add the booking to your calendar, email a confirmation.
- **A task can pause for a phone call and resume afterwards.** Gemini calls `place_call`, the conversation pauses while our ElevenLabs voice agent is on the phone, and when the call ends Gemini picks the task back up with the transcript.
- **Structured outputs turn a messy phone call into facts.** Gemini reads the transcript and returns strict JSON (booked? time, party size, deposit in pence, other times offered, and *why* it failed: fully booked, no answer, voicemail...). The app uses that JSON to decide what happens next.
- **It handles real-world failures.** Fully booked but you said "or later"? Gemini calls back once to book the time they offered. No answer? One retry. Voicemail? It doesn't pester the restaurant; it tells you. Never more than 2 calls per task.
- **It remembers the conversation.** Your agent's recent tasks go into Gemini's context, so "OK, book the 8:30 one" just works.
- **Per-agent permissions are enforced at the model level.** Gemini is only *given* the tools an agent is allowed to use (phone, calendar, email, payments), so a disabled tool can't be called.

**Safety rails (talking points)**

- Gemini never sees or chooses phone numbers: it picks a contact from our list and the server looks up the number, so it can't dial a number it made up.
- The task and user are bound by the server, not chosen by the model.
- Payments always need the user's approval in the app, and only Stripe **test** keys are accepted.
- Gemini is told never to claim something happened that a tool didn't confirm (e.g. "deposit paid"), and it doesn't put unconfirmed bookings in your calendar.

**Model**: `gemini-3.1-flash-lite` through the `google-genai` Python SDK: fast (2-4 s per step), and its free-tier limits (500 requests/day, 15/min) fit a live demo; one full booking takes about 6 requests.

## Evidence (what we tested)

Eight varied requests, each sent to a fresh agent through the real API and database (calls via the stand-in until the voice line is live):

| # | Request | What Gemini did | OK |
|---|---|---|---|
| 1 | Table for 2 at The Ivy this Friday 7:30pm | Looked up The Ivy, called: "Book a table for 2 on Friday 30 October 2026 at 19:30" | ✅ |
| 2 | Haircut at Barber Joe's (not a contact) | No call; "The only business I have available to call is The Ivy Oxford" | ✅ (after tuning) |
| 3 | Dentist next Monday 3pm, add to calendar | Calendar event Mon 26 Oct 15:00-16:00, no call | ✅ |
| 4 | "Book a table" | Asked for restaurant, date, time and party size | ✅ |
| 5 | "What's the weather?" | Said it can't, listed what it can do | ✅ |
| 6 | Cancel tonight's booking at The Ivy | Called with goal "Cancel my booking for tonight" | ✅ |
| 7 | Book The Ivy, agent without phone permission | "Please enable the phone permission"; nothing added | ✅ (after tuning) |
| 8 | 6 people at 7pm, "7:30 or 8 if needed", deposit up to £30 | Called with goal 19:00, fallbacks 19:30 / 20:00, deposit limit as a constraint | ✅ |

After-call scenarios (practice calls with `scripts/fake_call_end.py`):

| Situation | Result |
|---|---|
| Booked, £20 deposit | Calendar event at the right UK time, summary says the deposit still has to be paid (or "paid" once approved) |
| Fully booked, user said "or later" | Called back once for the offered time, booked, calendar at 20:30 |
| Fully booked, one exact time | No call back; told the user 8:30pm was offered |
| No answer twice | Retried once, then stopped and explained |
| Voicemail | No call back; explained and suggested next steps |
| Follow-up "Yes please, book the 8:30 one" | Worked out restaurant, party size and day from the earlier task and called |

**Prompt fixes found by testing**: Gemini asked users for phone numbers (now: only saved contacts), put unconfirmed bookings in the calendar when it had no phone permission (now: tells you to turn the permission on), returned empty answers when it had no tools (now told explicitly), and got the 25 Oct BST→GMT clock change wrong (now the server attaches UK time zones itself).

## Where it lives in the code

- `backend/app/orchestrator/loop.py`: manual function-calling loop (pause/resume, tool errors returned to the model).
- `backend/app/orchestrator/runner.py`: starts a task: per-agent tools, recent-task context.
- `backend/app/orchestrator/outcome.py`: structured-output extraction from call transcripts.
- `backend/app/orchestrator/callbacks.py`: `on_call_finished`: wrap-up, one call back, summary.
- `backend/app/orchestrator/prompts.py`: the system prompt rules above.
