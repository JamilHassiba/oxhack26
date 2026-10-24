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
