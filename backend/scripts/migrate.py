"""Applies the SQL files in backend/migrations/ in order to DATABASE_URL. Owner: Jamil.

Run from backend/:  python -m scripts.migrate

Each file runs once, inside a transaction, and is recorded in schema_migrations.
Files starting with the line `-- migrate: no-transaction` run outside a transaction
(needed for TimescaleDB continuous aggregates).
"""

import sys
from pathlib import Path

import psycopg

from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
NO_TRANSACTION = "-- migrate: no-transaction"


def main() -> int:
    url = get_settings().database_url
    if not url:
        print("DATABASE_URL is empty. Fill it in .env at the repo root.")
        return 1

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

        pending = [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in applied]
        if not pending:
            print("Database is up to date.")
            return 0

        for path in pending:
            sql = path.read_text()
            print(f"Applying {path.name}...")
            if sql.startswith(NO_TRANSACTION):
                # One statement at a time: Postgres wraps a multi-statement string in a transaction.
                for statement in sql.split(";\n"):
                    if any(line.strip() and not line.strip().startswith("--") for line in statement.splitlines()):
                        conn.execute(statement)
                conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            else:
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
        print(f"Applied {len(pending)} migration(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
