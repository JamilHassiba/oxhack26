# Frontend integration

Vite + React + TypeScript. Run `npm ci` then `npm run dev`. `npm run build` emits `dist/`; the server needs SPA history fallback. `/api` proxies to port 8000 in development. Production builds use `VITE_DEMO_MODE=false`, a same-origin `/api` reverse proxy, and unbuffered SSE. Environment values are public build inputs; never put secrets in `VITE_` variables.

## Contract and ownership

`src/types.ts` is the agreed wire contract in `docs/PLAN.md`. This change does not modify those types or any backend files. Components call the adapter in `src/api.ts`; backend naming/response changes belong there. `src/history-types.ts` contains UI-only projections. Scenario metadata belongs to the local simulator and is never sent to FastAPI.

| Request | Expected result |
| --- | --- |
| `GET /agents` | `Agent[]` |
| `POST /agents` | `{name, persona, voice, tools}` → `Agent` |
| `GET /agents/{id}` | `Agent` |
| `PATCH /agents/{id}` | partial agent fields → updated `Agent` |
| `DELETE /agents/{id}` | empty 204 or JSON acknowledgement |
| `GET /agents/{id}/tasks` | `Task[]`, the same joined shapes as task detail |
| `POST /agents/{id}/chat` | `{message}` → `{task_id}` |
| `GET /tasks/{id}` | `Task` |
| `POST /payments/{id}/approve` or `/deny` | empty 204 or JSON acknowledgement |
| `GET /calendar` | `CalendarEvent[]` |
| `GET /calendar.ics` | calendar attachment |
| `GET /analytics/summary` | `Analytics` |
| `GET /calls/{id}/events/stream` | SSE JSON `{ts, call_id, kind, payload: {speaker?, text?}}` |

The updated plan agrees PATCH for tools and the task-list endpoint. Agent management additionally needs PATCH of `name`, `persona`, and `voice`, plus DELETE. Those operations are isolated in the adapter and covered by mocked-server tests; they are not claimed to work against an unimplemented backend. Backend DELETE should reject active tasks/payments with 409 and preserve task history, preferably by archiving the agent. Duplication uses the existing POST endpoint and copies configuration only.

Payments use integer pence (`2000` = £20). Voices are labels mapped by Jamil. Tool permissions are `phone`, `email`, `calendar`, and `payments`. Chat is locked while a task runs; follow-up questions are answered with a new task, as agreed in PLAN.md.

## History and agent management

Live task history and chat use `GET /agents/{id}/tasks`, not browser-created task IDs. A fresh browser sees all tasks returned for the current agents. History searches requests, summaries, agent names, and transcript text, with status/agent filters and direct `/history/{id}` views. Failed agent-list requests show an error; failed individual task-list requests show partial results and a retry. Filters survive detail navigation and reload via URL parameters.

Deleting an agent is blocked while a task or approval is active. The adapter rechecks before DELETE; the backend remains responsible for enforcing this atomically. The frontend retains a labelled archived copy of completed tasks after deletion in that browser. A server-wide archived history endpoint is not assumed, so deleted-agent history on other devices depends on backend archival support. If local storage fails, the archive remains available in memory and the UI reports that it will not survive reload.

Agent edit/duplicate dialogs preserve instructions, voice, and selected permissions. Failed saves keep the form and draft. The picker maintains separate unsaved permission choices while switching agents. Enter saves changes before navigating.

## Demo scenarios

Demo mode is on by default, needs no backend, and never calls or charges anyone. In chat with a phone-enabled agent, choose:

- Successful booking: approve the £20 test deposit.
- Declined deposit: manually decline when prompted; approval is never automated.
- No answer: ringing followed by a failed task.
- Fully booked: transcript and failure, without payment or calendar entry.
- Alternative time: the agreed 7pm fallback is confirmed without a deposit.

These are fixed restaurant fixtures, not AI interpretation of the request. Agents without phone permission complete a generic simulated request. Every run snapshots its scenario, agent identity, and permissions at submission, so later edits cannot alter an in-flight rehearsal. State persists across reload, stages are idempotent, and the original demo storage format is migrated without clearing existing history.

## Checks

`npm run build`, `npm test`, `npm run format:check`; for browser checks, `npx playwright install chromium` then `npm run test:e2e`. Tests cover desktop/mobile workflows, permission snapshots, blocked deletion, archived history, all scenarios, API failures, SSE, and the agreed server task list. `npm run api:generate` remains available once FastAPI publishes its OpenAPI schema. Real backend integration and deployment are separate from these mocked checks.

## Feature files

- `src/features/agents/`: editing, duplication, and safe deletion.
- `src/features/history/`: search, filters, and task detail.
- `src/features/demo/`: local scenario controls and fixture definitions.
- `src/components/`: shared UI and call/payment cards.
- `src/demo.ts`: persistent local simulator; `src/api.ts`: only HTTP boundary.

The core stylesheet and backend-owned files were left unchanged by the feature work. New feature styles live in `src/features/features.css`.
