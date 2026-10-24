"""All DB tests use a fresh schema in an explicitly supplied TEST_DATABASE_URL."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings

USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def database(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable local PostgreSQL database.")
    schema = "evan_test_" + uuid4().hex
    root = Path(__file__).resolve().parents[2]
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        # Exercise Jamil's actual tables, defaults, constraints and seed data.
        # Plain local PostgreSQL cannot install TimescaleDB: only its extension
        # and hypertable conversion are omitted; the call_events table is real.
        base = (root / "migrations/001_init.sql").read_text()
        base = base.replace("CREATE EXTENSION IF NOT EXISTS timescaledb;", "")
        base = base.replace(
            "SELECT create_hypertable('call_events', by_range('ts', INTERVAL '1 day'));",
            "",
        )
        conn.execute(base)
        conn.execute(
            (root / "migrations/100_evan_agent_archival_email.sql").read_text()
        )
        conn.execute(
            "UPDATE users SET email = %s WHERE id = %s",
            ("demo@example.com", USER_ID),
        )
    options = f"-csearch_path={schema}"

    @asynccontextmanager
    async def connection():
        async with await psycopg.AsyncConnection.connect(url, options=options) as conn:
            yield conn

    def sync():
        return psycopg.connect(url, options=options)

    # Tools use the same isolated test schema; HTTP providers are mocked separately.
    monkeypatch.setattr("app.tools.calendar.connection", connection)
    monkeypatch.setattr("app.tools.email.connection", connection)
    yield connection, sync
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def client(database):
    _, sync = database
    with sync() as conn:
        schema = conn.execute("SELECT current_schema()").fetchone()[0]
    app = create_app(
        Settings(
            database_url=make_conninfo(
                os.environ["TEST_DATABASE_URL"], options=f"-csearch_path={schema}"
            ),
            gemini_api_key="",
            _env_file=None,
        )
    )
    # Exercise the shared app lifecycle and pool, using only the isolated schema.
    with TestClient(app) as client:
        assert client.get("/health").json()["db"] == "ok"
        yield client
