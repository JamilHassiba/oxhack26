# Team Plan (3 people, ~30 hours)

Companion to [DESIGN.md](DESIGN.md). Read that first for architecture, data model and API.

**Updated after the frontend was finished.** Evan's UI is done and merged, so he now takes some backend work and the deployment. The lists below are what's **left**, in priority order: do the top item first.

| | Jamil: Voice & Data | Alex: Orchestrator | Evan: Frontend, API & Deploy |
|---|---|---|---|
| Owns | ElevenLabs, Twilio, webhooks, call events, Tiger Data, migrations | Gemini loop, chat endpoint, call tool, payments | Frontend, agents/tasks/calendar API, email + calendar tools, Vultr deploy |
| Sponsors | ElevenLabs, Tiger Data | Gemini API | Vultr, DEV challenge, demo/pitch |
| Main files | `services/elevenlabs.py`, `services/events.py`, `routers/{webhooks,events,analytics}.py`, `migrations/` | `orchestrator/`, `tools/{phone,payments}.py`, `routers/{chat,payments}.py` | `frontend/`, `routers/{agents,tasks,calendar}.py`, `tools/{calendar,email}.py`, `deploy/` |

## Status

| Who | Done | In progress |
|---|---|---|
| Jamil | Design docs, repo skeleton | DB + migrations, voice spike |
| Alex | Backend skeleton, call contract, Gemini loop with a fake tool (on branches, not merged yet) | Merging to main |
| Evan | **Frontend MVP merged to main.** All pages built, works fully in demo mode, build + 10 tests pass | Backend tasks below |

## Decisions from the frontend review

The frontend was built before the backend existed, so it assumes some things the design didn't have. These are now decided, so nobody needs to discuss them again:

1. **The frontend's types are the API contract.** `frontend/src/types.ts` defines exactly what each endpoint returns (`Agent`, `Task`, `Payment`, `CalendarEvent`, `CallEvent`, `Analytics`). The backend returns those shapes. If you need to change one, tell Evan.
2. **Agents have a `voice` label**, not a voice ID (for example `"Warm & natural"`). Jamil maps labels to ElevenLabs voice IDs in his code.
3. **New endpoints:** `PATCH /agents/{id}` (save an agent's tools) and `GET /agents/{id}/tasks` (list an agent's tasks). The second one lets the frontend stop remembering task IDs in browser storage, which would break if the demo runs on a different laptop.
4. **Payment amounts are whole pence**: `2000` means £20. Payments also have a `merchant` name.
5. **`start_call` returns our `call_id`** (the ID of the `calls` row), not the ElevenLabs conversation ID. `on_call_finished` takes the same `call_id`. Everything else in Alex's contract (`backend/app/contracts.py` on his branch) stays as he wrote it.
6. **Where phone numbers come from:** a `contacts` table seeded with the demo restaurant, pointing at a teammate's phone. Alex adds a `lookup_contact` tool so Gemini can find the number.
7. **Follow-up questions:** the chat box is locked while a task runs, so the agent can't ask a question mid-task. If information is missing, the task ends with a summary asking for it, and the user sends a new message. Alex includes the agent's last few tasks (goal + summary) in Gemini's context so the new message has context.
8. **Call events use Evan's format:** `{ts, call_id, kind, payload: {speaker?, text?}}`, with the kinds `dialing`, `ringing`, `answered`, `transcript_line`, `tool_call`, `payment`, `ended`. Jamil writes this into `docs/EVENTS.md`.
9. **Demo mode stays as a backup.** The frontend's built-in simulated demo (`VITE_DEMO_MODE`, on by default) is our fallback if real calls fail on stage. The production build sets `VITE_DEMO_MODE=false`.

## Jamil: Voice & Data

1. **Database first (unblocks everyone).** Create the Tiger Cloud DB, share the connection string, and write `migrations/001_init.sql` with the decisions above (`agents.voice`, `payments.amount` in pence + `merchant`, `contacts` table seeded with the demo restaurant, `call_events` hypertable). Write `scripts/migrate.py`.
2. **`docs/EVENTS.md`** using decision 8.
3. **Voice spike:** ElevenLabs agent + Twilio number, one outbound call to your phone. Find out whether the transcript is available during the call or only after. Write the answer in `EVENTS.md`.
4. **`start_call`:** first a stub that inserts the `calls` row and returns `call_id` (hand to Alex straight away), then the real ElevenLabs call with the allowlist and duration cap.
5. **Post-call webhook:** store transcript, summary and outcome on `calls`, emit `ended`, then call Alex's `on_call_finished(call_id)`.
6. **Mid-call payment tool:** `request_payment_approval` creates a `pending_approval` payment and waits (with a timeout) for the user to approve in the UI.
7. **Live events:** `GET /calls/{id}/events/stream` (SSE). If the spike says live transcripts aren't possible, replay the stored transcript as events.
8. **Analytics:** continuous aggregate + `GET /analytics/summary`, returning the `Analytics` type from the frontend.
9. Voice prompt tuning for the restaurant scenario. ElevenLabs + Tiger Data bullets for the submission.

**Done when:** a call placed from the app to a real phone produces a stored transcript and a live event stream.

## Alex: Orchestrator

1. **Merge your branches into main** (`p2/backend-skeleton`, `p2/call-contract`, `p2/gemini-loop`). Main's backend files currently hold only header comments, so keep your versions. Apply decision 5 to `contracts.py`.
2. **`POST /agents/{id}/chat`:** save the message, create the task, run `run_task` in the background, return `task_id`.
3. **`place_call` + `lookup_contact` tools**, wired to Jamil's `start_call` (use his stub until the real one lands).
4. **`on_call_finished(call_id)`:** read the transcript, extract the outcome (booked? time? deposit?), then have Gemini call the calendar and email tools and write the summary.
5. **Payments:** `POST /payments/{id}/approve` and `/deny`, then a Stripe test-mode charge after approval (`tools/payments.py`).
6. **Context for follow-ups** (decision 7).
7. **Robustness:** no answer, voicemail, fully booked (try the fallback time, at most 2 calls). Prompt tuning, low temperature, test with 5+ different requests.
8. Gemini bullets for the submission. Bug bash.

You **declare** the calendar and email tools to Gemini; Evan writes the functions behind them.

**Done when:** a chat message results in a call, a payment approval, a calendar event, an email and a summary, with no manual steps.

## Evan: Frontend, API & Deploy

1. **Deploy to Vultr early** (webhooks need a public HTTPS URL, so Jamil is blocked without it): Ubuntu VM, domain, Caddy (`deploy/Caddyfile`: HTTPS, serve `frontend/dist`, proxy `/api` with buffering off for SSE), systemd service for the backend (`deploy/oxhack-api.service`), and `deploy/deploy.sh`. Build with `VITE_DEMO_MODE=false`. Start with a hello-world backend. Jamil is backup if you get stuck.
2. **Agents API:** `GET/POST /agents`, `GET/PATCH /agents/{id}`, returning your `Agent` type.
3. **Tasks API:** `GET /tasks/{id}` and `GET /agents/{id}/tasks`, returning your `Task` type (joins the task with its call, payment, calendar event and call events). Then switch the frontend from browser storage to `GET /agents/{id}/tasks`.
4. **Calendar:** `create_calendar_event` function in `tools/calendar.py`, plus `GET /calendar` and `GET /calendar.ics`.
5. **Email:** `send_email` function in `tools/email.py` via Resend.
6. **Integration:** run the frontend against the real backend, `npm run api:generate`, fix any mismatches.
7. **Demo and submission:** demo script and rehearsal, record the fallback video (demo mode is perfect for this), README, DEV post, Devpost/MLH page and sponsor opt-ins.

**Done when:** the full demo runs on the deployed site against the real backend, and the demo-mode fallback video is recorded.

## Timeline and sync points

| Hour | Milestone | Who |
|---|---|---|
| Next 2h | DB live; Alex's branches merged; hello-world deployed on Vultr | All |
| 10 | **Vertical slice**: chat → call → summary in the UI | All |
| 18 | Payments, calendar, email working end to end | All |
| 24 | **Feature freeze**: live view and analytics done | All |
| 27 | Full rehearsal on production, fallback video recorded | All |
| 30 | Submission in (Devpost/MLH, DEV post, sponsor forms) | All |

Sync: 5-minute standup every 3 hours. Anyone blocked for more than 20 minutes says so immediately. Sleep in shifts; keep one person awake and on the demo-critical path at the end.

## Cross-dependencies (where people block each other)

- **Everyone needs Jamil's database.** That's why it's his first task.
- **Jamil needs Evan's deployment** for ElevenLabs webhooks (or a tunnel like ngrok in the meantime).
- Alex needs Jamil's `start_call` stub, then the real version.
- Alex's `on_call_finished` calls Evan's calendar and email functions. Agree the function signatures in the stub files first.
- Jamil's mid-call payment tool and Alex's approve/deny endpoints share the `payments` table and its statuses.
- Evan's tasks API reads tables written by Jamil (`calls`, `call_events`) and Alex (`tasks`, `payments`).

## Git workflow

Branch from `main` for each task (`jamil/db`, `alex/chat-endpoint`, `evan/agents-api`), merge back to `main` as soon as it works, then pull `main` before starting the next task. Keep branches short-lived: hours, not days.

## Submission checklist (owner in brackets)

- [ ] ElevenLabs: voice agent used for real calls, mention conversational AI + server tools (Jamil)
- [ ] Gemini API: function calling + structured extraction (Alex)
- [ ] Tiger Data: hypertable + continuous aggregate shown in the demo (Jamil)
- [ ] Vultr: deployed app URL on the submission (Evan)
- [ ] DEV post published (Evan)
- [ ] README with setup, architecture diagram, demo video (Evan)
- [ ] Devpost/MLH project page and sponsor challenge opt-ins (Evan)
