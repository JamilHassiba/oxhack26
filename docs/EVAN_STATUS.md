# Evan progress — 24 October 2026

## Frontend features (pushed first)

Commit `a102ce7` on `frontend`: searchable/filterable task history and task detail; agent edit, duplicate, and delete controls; five local rehearsal scenarios. Production history now uses the agreed server task-list endpoint. 18 logic/API tests and 26 desktop/mobile/mocked-server browser tests passed. The canonical frontend wire types were not changed.

## New responsibilities implemented on codex/evan-api-deploy

- Agents: list, create, fetch, patch metadata/permissions, and soft-delete with active-task protection.
- Tasks: joined task detail plus server-side per-agent history, preserving archived agent history by stable ID.
- Calendar: permission-enforced, retry-safe creation, JSON listing, and Unicode-safe .ics export.
- Email: owner-address confirmation through Resend, permission checks, stable provider idempotency keys, and durable delivery records.
- Deployment: Ubuntu bootstrap, private Node 24, Caddy static/proxy/SSE configuration, systemd unit, release build/switch/health-check/rollback script, and environment templates.
- Demo: reproducible simulated fallback recording, three screenshots, two-minute script/rehearsal checklist, and an unpublished submission draft.

Verification: 13 tests against a real disposable PostgreSQL database (provider requests mocked), Python formatting/import checks, OpenAPI generation for the owned routes, Caddy configuration validation using the official binary, and shell syntax checks. These are not claims of successful Vultr deployment or real phone/email integration.

## Local integration completed

Main through `762bd45` is merged without conflicts. The shared app now registers Evan's routers with one import and one registration call. Alex's config/schemas/orchestrator and Jamil's DB pool/events/base migration are unchanged.

All 21 backend tests pass. Database tests now use the shared app's real pool and Jamil's actual base migration, including defaults, constraints and seed data, rather than a duplicate test schema. Only TimescaleDB extension setup and hypertable conversion are omitted for plain local PostgreSQL.

A browser check passed against React → Vite proxy → shared FastAPI → disposable PostgreSQL: creating an agent, saving tool permissions, retaining them after reload, reading empty history, and exporting ICS. `frontend/src/openapi.d.ts` is generated from the shared app's currently registered routes.

## Deferred and remaining work

1. **Vultr deferred at Evan's request.** The account displays $100 promotional credit but requires a linked payment method. No VM was created and no card was linked. Continue using `docs/LOCAL_DEVELOPMENT.md`.
2. Apply both migrations to the shared Tiger database and validate TimescaleDB behavior; local table/constraint checks passed.
3. Integrate the remaining chat/payment/voice/analytics routes as their owners publish them. Regenerate the OpenAPI snapshot afterward.
4. Configure provider credentials, then verify real chat/call/payment/email completion. Provider requests in tests are mocked; no real email was sent.
5. Rehearse the real-service flow three times, add real evidence/URLs, then publish and submit. The committed fallback video is explicitly simulated.
