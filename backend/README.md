# Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
cp ../.env.example ../.env                                 # fill in GEMINI_API_KEY, DATABASE_URL, ...
.venv/Scripts/python run.py                                # http://127.0.0.1:8000/health, /docs
.venv/Scripts/python -m pytest
```

**On Windows, start the backend with `python run.py`, not uvicorn** (psycopg's async pool needs a selector event loop).
Mac and the Vultr server use uvicorn as normal: `uvicorn app.main:app --reload`.
The frontend's Vite proxy sends `/api/*` to `http://localhost:8000/*`, so routes have no `/api` prefix.

Layout: `app/main.py` (app factory), `config.py`, `db.py` (psycopg pool, plain SQL), `routers/`.

## Gemini tool loop

`app/orchestrator/loop.py` runs model → tool call → result → model until Gemini answers in text. Tools are
`app/tools/base.Tool` specs (JSON-schema params + async handler); a tool with `ends_turn=True` pauses the loop
(used by `place_call`, resumed by `on_call_finished`). Tool errors go back to Gemini instead of crashing.

Spike against the real API (needs `GEMINI_API_KEY`):

```bash
.venv/Scripts/python -m scripts.gemini_hello "Can I get a table for 4 at Dishoom at 19:00?"
.venv/Scripts/python -m scripts.gemini_hello --list-models
```
