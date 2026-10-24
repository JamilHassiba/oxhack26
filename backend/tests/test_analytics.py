from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.routers import analytics

TODAY = date(2026, 10, 25)
AGENTS = [{"id": "maya", "name": "Maya"}, {"id": "sam", "name": "Sam"}, {"id": "new", "name": "New agent"}]


def call(agent, day, ended=True, success=False, duration=60.0):
    return {"agent_id": agent, "day": day, "ended": ended, "success": success, "duration_seconds": duration}


CALLS = [
    call("maya", date(2026, 10, 25), success=True, duration=40),
    call("maya", date(2026, 10, 25), success=False, duration=20),  # e.g. fully booked
    call("maya", date(2026, 10, 24), ended=False, duration=None),  # still on the phone: not in the rates
    call("sam", date(2026, 10, 20), success=True, duration=90),
    call("sam", date(2026, 10, 1), success=False, duration=None),  # older than the 7-day chart
]


def test_summary_numbers():
    s = analytics.summarise(CALLS, AGENTS, TODAY)

    assert s.total_calls == 5
    assert s.success_rate == 50.0  # 2 of the 4 finished calls booked
    assert s.avg_duration_seconds == 50.0  # (40 + 20 + 90) / 3 finished calls with a duration
    assert [d.date for d in s.calls_by_day] == [f"2026-10-{n}" for n in range(19, 26)]
    assert [d.calls for d in s.calls_by_day] == [0, 1, 0, 0, 0, 1, 2]
    assert [(a.name, a.calls, a.success_rate) for a in s.agents] == [
        ("Maya", 3, 50.0),
        ("Sam", 2, 50.0),
        ("New agent", 0, 0.0),
    ]


def test_no_calls_yet():
    s = analytics.summarise([], AGENTS, TODAY)

    assert (s.total_calls, s.success_rate, s.avg_duration_seconds) == (0, 0.0, 0.0)
    assert len(s.calls_by_day) == 7 and all(d.calls == 0 for d in s.calls_by_day)


def test_endpoint_matches_frontend_analytics_type(monkeypatch):
    async def fetch():
        return CALLS, AGENTS

    monkeypatch.setattr(analytics, "fetch", fetch)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        body = client.get("/analytics/summary").json()

    assert set(body) == {"total_calls", "success_rate", "avg_duration_seconds", "calls_by_day", "agents"}
    assert set(body["calls_by_day"][0]) == {"date", "calls"}
    assert set(body["agents"][0]) == {"name", "calls", "success_rate"}


def test_migration_runs_outside_a_transaction():
    sql = (Path(__file__).parents[1] / "migrations" / "002_call_stats.sql").read_text()
    # Jamil's migrate script only skips the transaction when this is the very first line.
    assert sql.startswith("-- migrate: no-transaction\n")
    assert "timescaledb.continuous" in sql
