# Presentation notes (Alex)

How Concierge works, what to say about each part, and answers to likely audience questions.
Status is as of 25 Oct 2026, ~03:00 UK: live site on `main` = `d3a09a9`. Update section 9 before presenting.

## 1. One sentence

You tell an AI agent what you want ("book a table for 4 at The Ivy tomorrow at 6pm"); it phones the
restaurant for you, asks before paying any deposit, puts the booking in your calendar and tells you what happened.

## 2. The parts

| Part | Technology | Built by |
|---|---|---|
| Website | React + TypeScript (Vite) | Evan, then Alex |
| API server | Python, FastAPI | Alex, Evan, Jamil |
| AI "brain" | **Gemini API** (`google-genai`), model `gemini-3.1-flash-lite` | Alex |
| Phone calls | **ElevenLabs** Conversational AI + **Twilio** (the real phone line) | Jamil |
| Database | **Tiger Cloud** (Postgres + TimescaleDB) | Jamil |
| Deposits | **Stripe test mode** (no real money) | Alex |
| Hosting | **Vultr** VM, Caddy (HTTPS), systemd | Evan, then Alex |

"Two brains, one job each": **Gemini** plans and uses tools but never talks on the phone; **ElevenLabs** only
holds the phone conversation, following a brief Gemini wrote.

## 3. What happens when you send a message

1. **Send** (`POST /agents/{id}/chat`): saves the message and creates a task in one transaction, locking the
   agent so a double click can't start two tasks (second one gets "still working on a task"). Replies at once
   (`202` + task id); Gemini runs in the background so the page never freezes.
2. **Context** (`orchestrator/runner.py`): the agent's name and personality, the rules, today's date, and its
   **last 5 tasks** as earlier chat turns (so "OK, book the 8:30 one" works). Gemini is only given the tools that
   agent is allowed (phone, calendar, email, payments); others are never declared, so they can't be called.
3. **Function-calling loop** (`orchestrator/loop.py`): manual function calling — Gemini asks for a tool, our code
   runs it, logs it, sends the result back; repeat until it answers in text (max 8 rounds). Tool errors go back
   to Gemini so it can recover. `place_call` **pauses** the loop while the phone call happens.

## 4. Gemini's tools

| Tool | Does | Detail worth mentioning |
|---|---|---|
| `lookup_contact` | Finds a business by name | Returns a contact ID, **never the phone number** |
| `place_call` | Starts the call | Our code looks the number up itself, builds the brief, calls Jamil's `start_call`, max **2 calls per task** |
| `create_calendar_event` | Adds to the calendar | Gemini gives UK clock time; our code attaches the timezone (it got the 25 Oct clock change wrong) |
| `send_email` | Confirmation email | Recipient is always the user |

Task ID, user and agent are bound by our code, never chosen by Gemini. The **brief** (in `contracts.py`):
task id, phone number, goal, user name, agent name, constraints ("party of 4", "deposit up to £30"),
fallbacks ("19:30, 20:00"). In a real test call the voice agent used the fallbacks on its own: 6pm was full,
it turned down 7pm (not allowed) and booked 6:30.

## 5. During the call: deposits

The voice agent calls our server tool `request_payment_approval` when the restaurant asks for a deposit:
it creates a pending payment, the **Approve/Deny card** appears on the website, and the tool waits up to
25 s for your click, then tells the voice agent what to say (approved / declined / "I'll confirm shortly").
Approve charges **Stripe's test card** (idempotency key per payment, so a retry never charges twice; only
`sk_test_` keys accepted). Every payment needs a human click.

## 6. After the call (`orchestrator/callbacks.py`)

1. Jamil's **post-call webhook** (signature-checked) saves the transcript and timeline, then calls `on_call_finished`.
2. **Structured output**: Gemini reads the transcript and must return JSON matching a strict schema
   (temperature 0): `result` (booked / fully_booked / no_answer / voicemail / declined / other), booked,
   time, party size, deposit, other times offered, reason.
3. **Code decides the next step**, not free text: booked → calendar + email + summary (task "done");
   fully booked with a time that fits what you asked, or no answer → **one** call back; voicemail, a plain no, or
   2 calls made → explain and stop (task "failed").
4. Gemini is told each payment's real status, so it only says "deposit paid" when it is.

## 7. Data and the Tiger Data showcase

Tables: users, agents, contacts, tasks, messages, calls, payments, calendar_events. **`call_events`** is a
TimescaleDB **hypertable** (the call timeline: dialing, transcript lines, payment, ended), streamed live to the
website (`GET /calls/{id}/events/stream`, server-sent events). **`call_stats_hourly`** is a **continuous
aggregate** over it (refreshed every 5 min + real-time), behind the Analytics page (`/analytics/summary`).

## 8. Likely audience questions

- **Why two AIs?** Gemini is good at planning and tool use; ElevenLabs at natural, low-latency voice. Keeping them
  apart also means Gemini's mistakes can't reach the person on the phone directly.
- **Why manual function calling?** Control: we log every call, return errors to the model, enforce limits (max 2
  calls) and pause a task mid-way for a phone call that can take minutes.
- **How do you stop it calling random numbers?** Gemini never sees or types numbers; it picks from saved contacts
  and the server looks the number up. (A `CALL_ALLOWLIST` can restrict further — not set on the live server.)
- **How do you stop it spending money?** Every payment needs your click; Stripe test keys only; idempotency keys.
- **What if Gemini makes something up?** The prompt forbids reporting what a tool didn't return; call facts go
  through a strict JSON schema; retry / done / failed decisions are made in code from that JSON.
- **What if Gemini is down or rate-limited?** The task is marked failed with a friendly message and the chat
  unlocks. Free tier: 500 requests/day on our model; a booking uses about 6.
- **Timezones?** Gemini gives UK wall-clock time and our code attaches Europe/London; the website always shows UK time.
- **How does it remember?** Last 5 finished tasks are replayed as earlier chat turns (long summaries truncated).
- **Why can't it ask questions mid-task?** Design choice: chat locks during a task; missing info → it ends with a
  question and you reply. The one mid-call question is deposit approval.
- **How long does a booking take?** Gemini steps 2-4 s each; the real test call took 62 s; message to "done" 92 s.
- **Does it disclose it's an AI?** It should open with "I'm an AI assistant calling on behalf of…" — being fixed (see 10).
- **Does it scale?** One server for the hackathon; async DB pool and background tasks would move to a job queue
  and more workers in production.
- **How was it tested?** 95 backend tests (fake Gemini), 22 website unit tests and 26 browser tests (desktop,
  phone, real mode against a mocked backend), real end-to-end runs on the shared database, an 8-request prompt
  evaluation (2 issues found and fixed), and a real phone call.

## 9. Be honest about what's live (update before presenting)

As of `d3a09a9`:
- **Real:** Gemini, the database, the website, real phone calls (ElevenLabs + Twilio), calendar, deposit approvals.
- **Simulated:** the Stripe charge (no `STRIPE_SECRET_KEY` on the server yet; approving marks it paid without Stripe).
- **Not set up:** email (no Resend key / `EMAIL_FROM`); the agent says honestly it couldn't send it.
- **Transcript timing:** on real calls the transcript currently appears **when the call ends**; the live version is
  on branch `alex/live-transcript`, waiting for a real-call test.
- **Not yet merged:** branch `alex/chat-call-view` (booking details table after calls, simpler chat header).

## 10. Messages to send Jamil

**Live transcript (before merging `alex/live-transcript`):**
> I've added a live transcript for real calls (branch `alex/live-transcript`). During a call it polls
> `GET /v1/convai/conversations/{id}` every 2s and writes new `transcript_line` events. I changed your webhook
> slightly: transcript parsing moved to `services/transcript.py` (shared, `EMOTION_TAG` still importable from
> webhooks), and `event_rows` now takes `skip_lines` / `answered_already` so lines written live aren't duplicated.
> Both lock the calls row. Your tests still pass. Shout if you'd rather do it differently!

**Voice prompt fixes (from the real test call):**
> 1. The opener should disclose it's an AI: "Hi, I'm {{agent_name}}, an AI assistant calling on behalf of
>    {{user_name}}…" (it currently skips "AI assistant").
> 2. It asked the restaurant "Could I get a name for the booking?" — it should *give* the name: "The booking is
>    under {{user_name}}."
>
> Next real test should include a deposit ("we need a £20 deposit") with an agent that has the payments
> permission, to check `request_payment_approval` is wired up in ElevenLabs.

**Payment tool config (if not done yet):** URL
`POST https://192-248-148-174.sslip.io/api/webhooks/elevenlabs/tools/request_payment_approval`, timeout 30 s;
body `call_id` = `{{call_id}}`, `amount` in pounds, optional `description`; optional header `X-Tool-Secret`
(matching `ELEVENLABS_TOOL_SECRET`, currently not set on the server). Response
`{status: approved|denied|pending|not_allowed|invalid, payment_id, message}` — the agent follows `message`.

## 11. Still to do before the demo

- Real-call test of the live transcript (deploy `7ea107f` as a preview, then merge both open branches).
- Delete the test agents on the live site (Demo, Josh, lkjbhkjl, Maya (live test)); rename the demo user from "Demo User".
- Optional: Stripe test key, Resend email.
- Rehearse 3 times (docs/demo/RUNBOOK.md); submission: Gemini bullets in docs/SUBMISSION_GEMINI.md, DEV post,
  Devpost page, sponsor opt-ins (ElevenLabs, Gemini, Tiger Data, Vultr, DEV).
