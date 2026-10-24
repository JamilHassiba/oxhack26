# Frontend integration notes

## Run and ship

From this directory: `npm ci`, then `npm run dev`. `npm run build` emits static assets into `dist/`. Serve those assets with history fallback (`try_files {path} /index.html` in Caddy) so routes such as `/chat/maya` work on refresh. Reverse proxy `/api/*` to FastAPI with the `/api` prefix stripped. Keep SSE buffering disabled and allow long-lived connections on the proxy.

Vite reads `VITE_DEMO_MODE` and `VITE_API_BASE_URL` at build time. Default is demo mode. Set `VITE_DEMO_MODE=false` before building the integrated app; use `/api` for same-origin requests. No secret belongs in a `VITE_` variable. This is the single-user hackathon UI described in the design; add authentication before exposing personal task data publicly.

## Provisional API contract

All JSON fields are defined in `src/types.ts`. No backend or OpenAPI schema was present when this frontend was built. These are integration assumptions to reconcile with Alex and Jamil, not an assertion of a working backend.

| Request | Expected result |
| --- | --- |
| `GET /agents` | `Agent[]` |
| `POST /agents` | body `{name, persona, voice, tools}`; returns `Agent` |
| `PATCH /agents/{id}` | body `{tools}`; returns updated `Agent`; saves checkbox permissions when entering an agent |
| `POST /agents/{id}/chat` | body `{message}`; returns `{task_id}` |
| `GET /tasks/{id}` | `Task`, including `goal`, `agent_id`, `created_at`, optional `call`, `payment`, `calendar_event`, `summary`, and `events` |
| `POST /payments/{id}/approve` or `/deny` | JSON result or HTTP 204; frontend refreshes task |
| `GET /calendar` | `CalendarEvent[]` |
| `GET /calendar.ics` | downloadable calendar |
| `GET /analytics/summary` | `Analytics` |
| `GET /calls/{id}/events/stream` | SSE, described below |

Tool values are `phone`, `email`, `calendar`, `payments`. Voice currently uses a descriptive label; replace labels with supported voice IDs when the backend exposes voice options. Payment amounts are **integer minor units** (`2000` = £20); confirm this with the backend before connecting approval cards.

Tasks poll every 1.2 seconds. Live mode remembers task IDs created in this browser because the sketch does not include a task-list or message-history endpoint; it cannot recover tasks created on other devices. Completed tasks continue to refresh for now to avoid missing eventual calendar/summary updates. Agent switching, navigation, and reload preserve task access. The agent picker shows one agent with previous/next arrows and four permission checkboxes. Draft permissions remain separate while switching; **Enter agent** saves them before navigating. Demo permissions persist locally. Live mode requires the provisional PATCH endpoint above and shows any save error without entering the agent. The last selected agent is remembered in this browser. There is one request/response task thread per message; longer conversational history should be integrated when the backend provides it.

SSE uses `EventSource`, supports unnamed frames and named event kinds from DESIGN.md (`dialing`, `ringing`, `answered`, `transcript_line`, `tool_call`, `payment`, `ended`). The full event is JSON `{ts, call_id, kind, payload: {speaker?, text?}}`. Messages with the same timestamp, kind, and payload are deduplicated. Native EventSource reconnects automatically; polling continues while reconnecting. It closes on task completion or component unmount. REST task state must include transcript/events for replay after refresh. Event timestamps should be unique per call event; include SSE `id:` values for resumable delivery. Confirm authoritative payloads with Jamil's future `docs/EVENTS.md`.

`npm run api:generate` fetches `http://localhost:8000/openapi.json` and generates `src/openapi.d.ts`. Use that schema to replace provisional contracts and adapt any response envelopes/field names before validating the integrated flow.

## Accessibility and interaction

High-contrast text, semantic navigation, labelled form controls, native modal focus containment and Escape handling, keyboard message submission (Shift+Enter for newline), reduced-motion support, approval disabled while submitting, and mobile layouts are included. Errors surface in the UI; HTTP requests time out after 15 seconds. User content is rendered as text, never injected HTML.

## Scope

Included: agent carousel/create, per-agent permission checkboxes, per-agent task threads, polling, SSE transcript/timeline, duration, summaries and failures, test payment approval/decline in chat and a dedicated Payments view, collapsed completed transcripts, calendar list/month/export, live aggregate charts, local persistent demo fixtures, and integration notes.

Not yet validated: real API calls, real SSE delivery, provider voice IDs, backend auth, production deployment, email delivery, and end-to-end real phone calls. Public DEV/Devpost posts and demo recording need the working deployment; no publication is performed by this frontend change.
