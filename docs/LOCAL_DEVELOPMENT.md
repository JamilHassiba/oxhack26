# Continue locally without Vultr

No Vultr account, card, server, domain or provider credentials are needed for the simulated demo. Cloud deployment is deferred. The simulation remains the complete booking demonstration while the real chat, voice and payment endpoints are being built.

## Full simulated flow

```sh
cd frontend
npm ci
VITE_DEMO_MODE=true npm run dev -- --host 127.0.0.1
```

Open http://localhost:5173. Select an agent's tools, enter it, and book a table. Rehearse the success and failure scenarios, payment decision, history and calendar export. All calls, emails and payments in this mode are simulated. [Fallback recording](demo/fallback-demo.webm) · [Demo script](demo/RUNBOOK.md).

## Real API work

Use a separate, disposable local PostgreSQL database for tests. The shared application now registers Evan's agent, task-history and calendar routes. Install and test from the repo root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-evan-test.txt
TEST_DATABASE_URL=postgresql://localhost/concierge_test PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```

Tests create and remove random schemas in that database. They use the actual shared migration's tables, defaults and constraints, omitting only TimescaleDB extension creation and hypertable conversion on plain PostgreSQL. Time-series behavior must still be checked against Tiger Data. Without `TEST_DATABASE_URL`, database-dependent tests skip explicitly.

For a normal live development database, configure `DATABASE_URL` locally and apply the shared migrations with `cd backend && python -m scripts.migrate` (requires TimescaleDB). Keep provider credentials empty to avoid real service calls. Start the API:

```sh
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
VITE_DEMO_MODE=false npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Open http://localhost:5174. Agent creation and permissions, task reads and calendar export use the real API/database. Chat, payment actions, live call streams and analytics need the remaining backend routes; live mode does not silently simulate them. `/health` reports database connectivity. Do not expose this single-user development app publicly.

`npm run api:generate` in `frontend/` refreshes the generated schema from localhost:8000. The checked-in snapshot covers only currently registered routes; the handwritten types remain the team's agreed contract.
