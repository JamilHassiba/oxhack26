# Team Plan (3 people, ~30 hours)

Companion to [DESIGN.md](DESIGN.md). Read that first for architecture, data model and API.

| | Person 1: Voice & Infra | Person 2: Orchestrator & Tools | Person 3: Frontend |
|---|---|---|---|
| Owns | ElevenLabs, Twilio, webhooks, call lifecycle, Tiger Data, Vultr | Gemini loop, tool layer, chat/agents/tasks API | All React + TS UI, SSE, demo polish, DEV post |
| Sponsors | ElevenLabs, Tiger Data, Vultr | Gemini API | DEV challenge, demo/pitch |
| Main dirs | `backend/app/services/elevenlabs.py`, `routers/webhooks.py`, `migrations/`, `deploy/` | `backend/app/orchestrator/`, `tools/`, `routers/{agents,chat,tasks,payments}.py` | `frontend/` |

## Shared agreements (first hour, all three)

1. **Repo layout** and git flow: trunk-based, small PRs to `main`, rebase before merge. Each person works in their own directories to avoid conflicts.
2. **API contract**: agree endpoint shapes from DESIGN.md section 5. P2 owns the FastAPI route definitions; P3 generates the TS client from `/openapi.json` and mocks until routes land.
3. **`call_events.kind` values and payload shapes** (DESIGN.md section 4). P1 writes them, P2 and P3 read them. Write the payload shapes in `docs/EVENTS.md` before anyone codes against them.
4. **Env/secrets**: `.env.example` committed, real `.env` shared privately (ElevenLabs, Gemini, Twilio, Stripe test, Resend, DB URL).
5. **Demo scenario and who plays the restaurant** (decide before hour 3).

## Person 1: Voice & Infra

**Phase 0 (h0–3)**
- Create ElevenLabs Conversational AI agent; buy/verify Twilio number; connect it in ElevenLabs.
- Script: place an outbound call to a teammate's phone. **Spike:** what is available during the call (poll the conversation API?) versus only after (post-call webhook)? Write findings in `docs/EVENTS.md`. This decides the live-transcript approach.
- Create Tiger Cloud DB. Write migrations for all tables and the `call_events` hypertable. Share the connection string.

**Phase 1 (h3–10)**
- `services/elevenlabs.py`: `start_call(to_number, brief) -> conversation_id` using dynamic variables for the brief (goal, constraints, fallbacks, user name, AI-disclosure opener).
- `POST /webhooks/elevenlabs/post-call`: verify signature, store transcript and analysis on `calls`, emit `ended` event, trigger P2's `on_call_finished(call_id)`.
- Write `call_events` for every lifecycle step (dialing, answered, ended, plus transcript lines via polling if the spike allows).
- Phone allowlist and call duration cap in config.
- Deploy: Vultr VM, docker compose (backend, frontend static, Caddy), domain + HTTPS. Webhook URL registered with ElevenLabs. CI-less deploy script (`deploy/deploy.sh`).

**Phase 2 (h10–18)**
- Mid-call server tools: `POST /webhooks/elevenlabs/tools/{name}` for `request_payment_approval` and `check_calendar`. Hold the request until the user approves (poll the `payments` row, with timeout) or return "pending" and let the agent say it will follow up.
- Tune the voice agent prompt for the restaurant scenario: polite, concise, handles "full at 6pm" with the fallback times.

**Phase 3 (h18–24)**
- SSE endpoint `GET /calls/{id}/events/stream` reading `call_events` (LISTEN/NOTIFY or short polling).
- Continuous aggregate + `GET /analytics/summary` (calls per agent per hour, success rate, avg duration).
- Fallback if live transcript isn't possible: replay stored transcript through `call_events` with timing.

**Phase 4 (h24–30)**
- Production hardening: env vars, restart policies, logs. Rehearse the call end-to-end on the Vultr deployment. Record the fallback demo video. Write the Tiger Data and Vultr bullets for the submission.

**Done when:** a call placed from the deployed app to a real phone produces a stored transcript and a live event stream.

## Person 2: Orchestrator & Tools

**Phase 0 (h0–3)**
- FastAPI skeleton: app factory, config, db session (coordinate with P1), health route.
- Gemini function-calling hello world: one fake tool, confirm the loop (model → tool call → result → model) works with the SDK.

**Phase 1 (h3–10)**
- Agents CRUD (`/agents`) with `persona` and `tools` array.
- `POST /agents/{id}/chat`: create `tasks` row, run orchestrator, return `task_id` immediately (run loop as a background task).
- Orchestrator: builds the system prompt from agent name/persona, declares only the agent's enabled tools, executes the loop, stores `messages`, logs each tool call as a `call_events`-style task event.
- `place_call` tool: calls P1's `start_call`, sets task status `calling`, and ends the loop turn.
- `on_call_finished(call_id)`: resumes the loop with the transcript/outcome and lets Gemini write the summary. Saves `tasks.summary`.

**Phase 2 (h10–18)**
- `create_calendar_event` tool + `calendar_events` table + `GET /calendar` and `/calendar.ics`.
- `send_email` tool via Resend (confirmation to the user's email).
- Payments: Stripe test-mode PaymentIntent; `payments` rows; `POST /payments/{id}/approve|deny`; `charge` tool only runs after approval.
- Structured outcome extraction from the transcript (booked? time? deposit?) so the summary and calendar entry use real values.

**Phase 3 (h18–24)**
- Robustness: retries, schema validation of tool args, handling "no answer", "voicemail", "fully booked, use fallback time" (this can mean a second call, capped at 2).
- Prompt tuning for the demo scenario; low temperature; test with 5+ varied requests.

**Phase 4 (h24–30)**
- Bug bash on the full flow. Write the Gemini section of the submission (function calling, structured extraction). Help with the DEV post.

**Done when:** a chat message results in a call, a payment approval, a calendar event, an email and a summary, with no manual steps.

## Person 3: Frontend

**Phase 0 (h0–3)**
- Vite + React + TS + Tailwind + React Router + TanStack Query. Layout shell with nav (Agents, Chat, Calendar, Analytics).
- Typed API client generated from OpenAPI; local mock server or MSW with fixtures so work isn't blocked on the backend.

**Phase 1 (h3–10)**
- Agents page: list, create form (name, persona, voice, tool toggles).
- Chat page: message thread per agent, send message, task status chip, polling `GET /tasks/{id}`.
- Task card: shows summary when done.

**Phase 2 (h10–18)**
- Call card in chat: status, transcript (post-call), outcome.
- Payment approval card (amount, merchant, Approve/Deny) wired to the approve/deny endpoints.
- Calendar page: list/month view of events; "add to Google/Apple calendar" via `.ics` link.

**Phase 3 (h18–24)**
- Live call view: SSE hook for `call_events`; streaming transcript bubbles, event timeline (dialing → answered → payment → ended), call duration timer.
- Analytics page: charts from `/analytics/summary` (calls over time, success rate per agent).
- Empty/loading/error states; mobile-friendly enough for a projector.

**Phase 4 (h24–30)**
- Visual polish pass; seed 1–2 preset agents so the demo starts in one click.
- Write and rehearse the demo script (DESIGN.md section 10), run it 3 times on the deployed site.
- Write the DEV post and the Devpost/MLH submission text; screenshots and the fallback video.

**Done when:** the full demo can run from the browser alone, and every state (calling, awaiting approval, done, failed) looks intentional.

## Timeline and sync points

| Hour | Milestone | Who |
|---|---|---|
| 1 | Contracts agreed (repo, API, event kinds, env) | All |
| 3 | Hello-world deployed on Vultr; outbound test call works; Gemini tool loop works; UI shell runs on mocks | All |
| 10 | **Vertical slice**: chat → call → summary in UI | All |
| 18 | Payments, calendar, email working end to end | P1 + P2, P3 UI |
| 24 | **Feature freeze**: live view and analytics done | All |
| 27 | Full rehearsal on production, fallback video recorded | All |
| 30 | Submission in (Devpost/MLH, DEV post, sponsor forms) | All |

Sync: 5-minute standup every 3 hours. Anyone blocked for more than 20 minutes says so immediately. Sleep in shifts; keep one person awake and on the demo-critical path at the end.

## Cross-dependencies (where people block each other)

- P2 needs P1's `start_call` and the DB schema by about hour 4. P1 hands over a working stub early, even one that only inserts rows.
- P3 depends on P2's routes. Mock until they land, then switch the client base URL.
- P3's live view depends on P1's event stream. Until then, show events from polling `GET /tasks/{id}`.
- P1's mid-call payment tool waits on P2's `payments` endpoints (hour 10–12). Agree the table and statuses up front.

## Submission checklist (owner in brackets)

- [ ] ElevenLabs: voice agent used for real calls, mention conversational AI + server tools (P1)
- [ ] Gemini API: function calling + structured extraction (P2)
- [ ] Tiger Data: hypertable + continuous aggregate shown in the demo (P1)
- [ ] Vultr: deployed app URL on the submission (P1)
- [ ] DEV post published (P3)
- [ ] README with setup, architecture diagram, demo video (P3)
- [ ] Devpost/MLH project page and sponsor challenge opt-ins (P3)
