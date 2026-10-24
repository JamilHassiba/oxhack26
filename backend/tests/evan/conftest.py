"""All DB tests use a fresh schema in an explicitly supplied TEST_DATABASE_URL."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient
from app.evan.app import create_app
from app.evan.database import get_repository
from app.evan.repository import Repository
from app.evan.settings import EvanSettings

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
        conn.execute((Path(__file__).parent / "schema.sql").read_text())
        conn.execute(
            (root / "migrations/100_evan_agent_archival_email.sql").read_text()
        )
        conn.execute(
            "INSERT INTO users (id,email,name) VALUES (%s,%s,%s)",
            (USER_ID, "demo@example.com", "Demo User"),
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
    connection, _ = database
    app = create_app(
        EvanSettings(database_url="", resend_api_key="", email_from="", _env_file=None)
    )

    async def repository():
        async with connection() as conn:
            yield Repository(conn)

    app.dependency_overrides[get_repository] = repository
    # No production lifespan/pool or provider is opened by this test client.
    with TestClient(app) as client:
        yield client
