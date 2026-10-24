# Evan: API, tools, and deployment handoff

Frontend features were committed/pushed first as `a102ce7` on `frontend`. This follow-up is on `codex/evan-api-deploy`. Main through `762bd45` is merged. Integration adds only route registration to the shared `main.py`; Alex's config/schemas/orchestrator and Jamil's DB/event/base migration implementations are unchanged.

## Run and register

Install `pip install -r requirements-evan.txt`. It adds FastAPI >=0.121 so yielded DB dependencies use function scope and commit **before** an HTTP response is sent.

Run the shared app, which now registers Evan's routes:

```sh
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The shared `create_app()` includes this registration:

```python
from app.evan import register_routes
register_routes(app)
```

Register once. The adapters use the shared `app.db.get_pool()`. `app.evan.app:app` remains available as a standalone smoke app. No fake chat, payment, voice, or analytics endpoints are installed. Routes have no `/api` prefix; Caddy/Vite strip it.

## Database

Apply Jamil's base schema first, then `migrations/100_evan_agent_archival_email.sql` via the shared migration runner or psql. This separate, rerunnable migration adds `agents.archived_at`, `email_deliveries`, and an insert trigger protecting archived agents. Jamil's `001_init.sql` and runner are untouched. This SQL assumes the schema in DESIGN.md; validate it against his actual migration when available.

Agents are soft-deleted, preserving history and all foreign keys. The delete route locks the agent and rejects active tasks/payment approvals. The task-insert trigger obtains a compatible lock so a concurrent chat task cannot be inserted after archival; Alex should translate its `CheckViolation` into a 409 and should reject archived agents when starting a chat.

Single-user demo: POST /agents uses the first seeded `users` row. No user is silently invented. Multi-user ownership/authentication is outside the current agreed scope.

Implemented routes match `frontend/src/types.ts`: GET/POST agents, GET/PATCH/DELETE one agent, GET task detail, GET per-agent tasks, GET calendar, and GET calendar.ics. PATCH supports name, instructions, voice, and tools. DELETE returns 204. IDs are UUIDs, payment amounts are integers, dates carry offsets, optional task fields are omitted when absent, and provider/internal DB fields are excluded. A task uses its most recent call; multiple calls do not multiply history rows. Payment selection prioritizes a pending approval where more than one row exists.

## Functions for Alex

```python
await create_calendar_event(
    task_id=task_id, title='Dinner', starts_at='2026-10-25T18:00:00+00:00',
    ends_at='2026-10-25T19:30:00+00:00', location='Oxford',
)
await send_email(task_id=task_id, subject='Booking confirmed', body='Your table is booked.')
```

Imports are `app.tools.calendar.create_calendar_event` and `app.tools.email.send_email`. Bind `task_id` in the orchestrator rather than allowing Gemini to choose another task. Both enforce the agent's current tool permission. Calendar dates require explicit timezone offsets. Identical calendar retries reuse the event; conflicting retries return 409. The ICS feed escapes user text, uses UTC, and folds Unicode lines at 75 octets.

Email recipients come from the task owner's `users.email`; Gemini does not choose a recipient. Set `RESEND_API_KEY` and `EMAIL_FROM` in the service environment or repo/backend `.env`. Email uses plain text, a stable Resend idempotency key, and a DB delivery record. Repeating the same task/content reuses the result; changed content for that task returns 409. Failed/ambiguous provider requests remain retryable using that same key. No real email was sent during development; provider tests use a fake transport. See [Resend's API](https://resend.com/docs/api-reference/emails/send-email).

## Tests and integration

```sh
pip install -r requirements-evan-test.txt
PYTHONPATH=. TEST_DATABASE_URL=postgresql://.../disposable_test_db python -m pytest tests/evan -q
```

DB tests create a random schema, apply Jamil's actual base tables and seed data followed by the additive migration, and drop only that schema afterwards. On plain PostgreSQL only the TimescaleDB extension and hypertable conversion are omitted. Tests use the shared app's real connection pool and exercise SQL/joins/transactions, archival guards, tool permissions, calendar retries/export, and mocked provider failures. Do not use a production database for tests. Without TEST_DATABASE_URL, DB tests are skipped explicitly.

Local integration passed through React, Vite's proxy, the shared FastAPI app, and PostgreSQL: agent creation, permission persistence across reload, empty history, and ICS export. `npm run api:generate` produced `frontend/src/openapi.d.ts` for the currently registered health/agents/tasks/calendar routes. Regenerate when chat/payment/voice/analytics routes land. Tiger Cloud/Timescale behavior and real providers remain unverified. Vultr is deferred at the user's request; see `docs/LOCAL_DEVELOPMENT.md` for continuing locally.
