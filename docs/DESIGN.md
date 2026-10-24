# OxHack 26: Agent Concierge — System Design & Plan

Web app where users create named AI agents, give them tools (phone, email, calendar, payments), and chat tasks like "book a table for 4 at X at 6pm". The agent makes a real phone call, pays if needed, adds the event to the calendar, and shows the user a live transcript plus a summary.

Sponsor targets: **ElevenLabs** (phone voice), **Gemini API** (orchestrator brain), **Tiger Data** (Postgres + hypertable event log), **Vultr** (hosting), plus the DEV writing challenge.

Stack: FastAPI, Postgres (Tiger Cloud), React + TypeScript (Vite). No Docker.

---

## 1. Architecture

```
React + TS (Vite)
  chat UI · agent builder · live call view · calendar · analytics
        │  REST + SSE
        ▼
FastAPI backend
  ├─ /chat            → Orchestrator (Gemini function calling)
  ├─ /agents, /tasks  → CRUD
  ├─ /events/stream   → SSE of call_events to the UI
  ├─ /webhooks/elevenlabs  (post-call transcript, mid-call server tools)
  └─ Tool layer: phone · email · calendar · payments
        │                    │
        ▼                    ▼
Tiger Cloud (Postgres)   ElevenLabs Conversational AI ──► Twilio ──► restaurant phone
  hypertable call_events
```

Two brains, one job each:

- **Gemini (orchestrator).** Reads the user's chat message, plans, calls our tools via function calling, and writes the final summary. It never talks to the third party.
- **ElevenLabs agent (voice).** Holds the actual phone conversation. Per call we inject a brief (goal, constraints, fallbacks, caller identity) through dynamic variables / prompt override. During the call it can hit our **server tools** (webhooks), e.g. `check_availability_in_calendar`, `request_payment_approval`.

Gemini decides to call; ElevenLabs executes the call; the result comes back via webhook and Gemini finishes the task (payment, calendar, email, summary).

## 2. Core flow (book a table)

1. User messages the agent: "Book a table of 4 at X at 6pm."
2. `POST /chat` → orchestrator loads the agent's name, persona, and enabled tools, calls Gemini with tool declarations (only enabled tools).
3. Gemini calls `place_call(phone, goal, constraints, fallbacks)`. Backend creates a `tasks` row and a `calls` row, then starts an ElevenLabs outbound call (`/v1/convai/twilio/outbound-call`) with the brief as dynamic variables.
4. During the call, events are written to `call_events` (hypertable) and streamed to the UI over SSE.
5. If payment is needed, the voice agent invokes the `request_payment_approval` server tool. The backend creates a `payments` row in `pending_approval`; the UI shows an Approve/Deny card. The tool returns the result to the voice agent mid-call (or it says "I'll follow up").
6. Call ends. ElevenLabs post-call webhook delivers transcript + analysis. We store it, then resume the Gemini loop with the call outcome.
7. Gemini calls `create_calendar_event`, optionally `send_email` (confirmation), then writes a summary. The UI shows summary, transcript, payment, calendar entry.

## 3. Tools

| Tool | Implementation | Hackathon scope |
|---|---|---|
| Phone | ElevenLabs Conversational AI agent + Twilio number, outbound-call API | Real. **Demo mode** routes to a teammate's phone. |
| Email | Resend (or SMTP) | Real, trivial. Confirmation emails to the user. |
| Calendar | Internal `calendar_events` table + `.ics` download; Google Calendar as stretch | Internal first. |
| Payments | Stripe **test mode** (PaymentIntent) behind an approval gate | Test mode only. Never real money. |

Per-agent tool permissions live in `agents.tools` (JSON array). The orchestrator only declares the enabled tools to Gemini, so a disabled tool can't be called.

Safety rails (also good demo talking points):
- Voice agent opens with "I'm an AI assistant calling on behalf of <user>".
- Real outbound calls only to an allowlist of numbers in `.env` (demo + teammates) unless explicitly toggled.
- Every payment requires user approval in the UI.
- Hard cap on call duration and one call per task by default.

## 4. Data model (Postgres / Tiger Cloud)

```sql
users(id, email, name, phone)                    -- single demo user is fine
agents(id, user_id, name, persona, voice_id, tools jsonb, elevenlabs_agent_id, created_at)
messages(id, agent_id, role, content, created_at)         -- chat history
tasks(id, agent_id, goal, status, summary, created_at)    -- status: planning|calling|awaiting_approval|done|failed
calls(id, task_id, to_number, el_conversation_id, status, started_at, ended_at,
      transcript jsonb, summary, outcome jsonb)
payments(id, task_id, amount, currency, status, stripe_pi_id)  -- pending_approval|approved|paid|denied
calendar_events(id, task_id, title, starts_at, ends_at, location)

-- Tiger Data: time-series event log
call_events(ts timestamptz, call_id, kind text, payload jsonb)
  SELECT create_hypertable('call_events', 'ts');
  -- kind: dialing | ringing | answered | transcript_line | tool_call | payment | ended
```

Tiger Data usage to show off:
- `call_events` as a hypertable: the live transcript and the event timeline are queries over it.
- A **continuous aggregate** for the analytics page: calls per agent per hour, success rate, avg duration.
- (Stretch) full-text/pgvector search over past transcripts for agent memory.

## 5. API sketch (FastAPI)

```
POST   /agents                    create agent (name, persona, tools, voice)
GET    /agents, GET /agents/{id}
POST   /agents/{id}/chat          send message → starts/continues a task; returns task_id
GET    /tasks/{id}                task + call + payment + calendar state
GET    /calls/{id}/events/stream  SSE of call_events (live transcript)
POST   /payments/{id}/approve | /deny
GET    /calendar                  events (+ /calendar.ics)
GET    /analytics/summary         from the continuous aggregate
POST   /webhooks/elevenlabs/post-call
POST   /webhooks/elevenlabs/tools/{tool_name}   mid-call server tools
```

Backend layout: `backend/app/{main.py, config.py, db.py, models.py, routers/, orchestrator/, tools/{phone,email,calendar,payments}.py, services/{elevenlabs,gemini}.py}`. Use async SQLAlchemy or psycopg + plain SQL (plain SQL is fastest for the hypertable stuff). Background work (the Gemini loop after a call ends) runs as FastAPI background tasks; no queue needed.

## 6. Frontend (React + TS, Vite)

Pages:
1. **Agents**: list + create form (name, persona, voice, tool checkboxes).
2. **Chat**: message thread with an agent; task status chips; inline cards for call, approval, calendar event.
3. **Live call view**: streaming transcript (SSE) with event timeline, then summary. Show both: transcript for the live "wow", summary after.
4. **Calendar**: simple list/month view of created events.
5. **Analytics** (stretch): calls over time from Tiger Data.

Libs: Vite, React Router, TanStack Query, Tailwind. Generate a typed client from FastAPI's OpenAPI schema so front/back stay in sync.

## 7. Deployment (Vultr)

No Docker. One Ubuntu VM on Vultr:

- **Backend:** repo cloned to the VM, Python virtualenv, uvicorn run as a `systemd` service (`deploy/oxhack-api.service`) so it restarts on crash and reboot.
- **Frontend:** `npm run build` (Vite) produces static files in `frontend/dist`.
- **Caddy** (`deploy/Caddyfile`): automatic HTTPS, serves `frontend/dist`, proxies `/api/*` to uvicorn.
- **Deploy:** `deploy/deploy.sh` runs git pull, installs dependencies, runs migrations, builds the frontend and restarts the service.
- **Database:** Tiger Cloud, used for both local development and production. No local Postgres needed.

A public HTTPS domain is required for ElevenLabs webhooks, so deploy a hello-world early rather than at the end.

Local development: backend with `uvicorn app.main:app --reload` in a virtualenv; frontend with `npm run dev` (Vite dev server on port 5173, with a Vite proxy sending `/api` to `localhost:8000`). Use a tunnel (ngrok / cloudflared) to receive ElevenLabs webhooks locally.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Live transcript during a phone call may not be streamable.** Phone calls via Twilio don't expose the client websocket; transcript may only arrive post-call. | **Spike first (Phase 0).** Try polling `GET /v1/convai/conversations/{id}` during the call. Fallback: write transcript on webhook and replay it with timing in the UI, and stream the events we do control (dialing, tool calls, payment). |
| Real restaurant doesn't answer / mishears | Demo mode: call a teammate who role-plays. Keep a recorded fallback video. |
| Twilio trial limits (verified numbers only, trial message) | Verify teammate numbers up front; or buy a number early. |
| Gemini tool-calling flakiness | Few tools, strict schemas, low temperature, explicit retry; log every tool call to `call_events`. |
| Webhooks can't reach localhost | Tunnel in dev, Vultr early. |
| Scope creep | Cut list below. |

## 9. Plan (≈ 30 hours, team of 3)

Split by ownership (details per person in [PLAN.md](PLAN.md)):

- **Jamil: Voice & infra.** ElevenLabs + Twilio, call lifecycle and webhooks, Vultr deploy, Tiger Data schema/migrations.
- **Alex: Orchestrator & tools.** Gemini loop, tool layer (phone wrapper, email, calendar, payments), chat/agents/tasks API.
- **Evan: Frontend.** Everything in React + TS (Vite), SSE live view, analytics page, then demo polish and the DEV post.

The shared contract is the OpenAPI schema plus the `call_events` kinds in section 4. Agree both in the first hour so the three can work in parallel.

**Phase 0: Spikes and skeleton (hours 0–3)**
- Jamil: ElevenLabs agent + Twilio number; place one outbound call from a script to a teammate's phone; inspect what the API gives during/after the call (transcript timing). Tiger Cloud DB and schema + hypertable migrations.
- Alex: FastAPI skeleton (shared with Jamil for config/db), Gemini function-calling hello world with one fake tool.
- Evan: Vite + React + TS app in `frontend/`, routing, Tailwind, API client shell against mocked responses.
- Together (end of phase): Vultr VM + domain with Caddy and the systemd service, hello-world deployed.

**Phase 1: Vertical slice (hours 3–10)**
Chat → Gemini → `place_call` → call → post-call webhook → summary shown in the UI. No payments/calendar yet. End of phase: the end-to-end demo works for one scenario.

**Phase 2: Remaining tools (hours 10–18)**
Calendar (table + .ics), email (Resend), payments (Stripe test + approval card + mid-call server tool). Agent builder with per-agent tool permissions.

**Phase 3: Live experience (hours 18–24)**
SSE live transcript/timeline from `call_events`, call view polish, analytics page via continuous aggregate (Tiger Data showcase).

**Phase 4: Polish and submit (hours 24–30)**
Demo script and rehearsal (3×), recorded fallback video, README, DEV post, sponsor checklist, Devpost/MLH submission. Freeze features at hour 24.

**Cut list if behind (in order):** analytics page → Google Calendar → email → transcript search → multi-agent creation UI (ship with 1–2 preset agents).

With three people there is no spare capacity: the first cut is the analytics page (Tiger Data continuous aggregate stays as a backend-only query if the UI is cut), and Jamil starts helping Alex as soon as the voice path is stable.

## 10. Demo script (2 minutes)

1. Create agent "Maya" with all four tools (10 s).
2. Type: "Book a table for 4 at <demo restaurant> tonight at 6pm; they may ask for a deposit."
3. Watch Maya call a teammate's phone; the live transcript scrolls.
4. Teammate asks for a £20 deposit; an approval card appears; approve.
5. Calendar entry and email confirmation appear; the summary card finishes the task.
6. Flash the analytics page and mention the Tiger Data hypertable and Vultr deployment.

## 11. Open questions

- Which demo restaurant / who plays it live?
- Twilio number: trial vs paid (UK number for the call)?
- Is auth needed? Proposal: no, a single seeded demo user.
- Confirm sponsor judging criteria for ElevenLabs, Gemini, Tiger Data and Vultr with their mentors at the event.
