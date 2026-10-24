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

## Shared files left untouched

Alex's shared app/config/schemas/orchestrator, Jamil's DB pool/event/voice/base migration, and both design/plan documents remain unchanged by this implementation. The five assigned router/tool files are implemented in place; support code is namespaced under `app/evan/`. The extra migration is separate from Jamil's base migration.

Alex's current `p2/backend-skeleton` branch contains stale ownership-comment changes in these five stub files. If merging it produces comment conflicts, keep Evan's implemented router/tool versions; the old branch has no implementation in those stubs. The substantive shared app/db/config code is untouched here.

## Required integration and external work

1. Provision the Vultr VM and domain; none exists yet. Follow `deploy/README.md`; use HTTP smoke deployment before the real HTTPS domain if helpful.
2. Merge Alex's shared app and register the owned routers with `app.evan.register_routes(app)`, as documented in `backend/EVAN_INTEGRATION.md`. The current standalone app deliberately exposes only health and Evan's routes.
3. Apply Jamil's base migration, verify its actual columns against the agreed design, then apply `100_evan_agent_archival_email.sql` through the shared migration process.
4. Configure the shared DB and provider credentials. No real email was sent in tests.
5. Generate the complete OpenAPI types after all shared routers are registered, then verify real chat/call/payment/email completion from the frontend.
6. Rehearse the deployed real-service flow three times, add the real evidence/URLs, then publish and submit. The video currently committed is explicitly simulated.
