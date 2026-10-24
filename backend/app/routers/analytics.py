"""Call analytics from the Tiger Data continuous aggregate. Owner: Jamil (built by Alex).

GET /analytics/summary reads call_stats_hourly (migrations/002_call_stats.sql), a continuous aggregate
over the call_events hypertable, and joins it to calls/tasks/agents for the per-agent breakdown.
A call is a success when it ended, Gemini's outcome says it was booked, and no deposit was declined.
"""

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from psycopg.rows import dict_row

from app import db
from app.schemas import AgentStats, Analytics, DayCalls

router = APIRouter(tags=["analytics"])

UK = ZoneInfo("Europe/London")
DAYS = 7

PER_CALL = """
WITH per_call AS (
    SELECT call_id, min(first_event_at) AS started_at, bool_or(ended) AS ended,
           max(duration_seconds) AS duration_seconds
    FROM call_stats_hourly
    GROUP BY call_id
)
SELECT a.id::text AS agent_id,
       (pc.started_at AT TIME ZONE 'Europe/London')::date AS day,
       pc.ended,
       pc.duration_seconds::float AS duration_seconds,
       (pc.ended
        AND coalesce((c.outcome->>'booked')::boolean, false)
        AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.task_id = t.id AND p.status = 'denied')) AS success
FROM per_call pc
JOIN calls c ON c.id = pc.call_id
JOIN tasks t ON t.id = c.task_id
JOIN agents a ON a.id = t.agent_id
"""
# Every current agent, plus archived ones that made calls (their history still counts).
AGENTS = """
SELECT a.id::text AS id, a.name FROM agents a
WHERE a.archived_at IS NULL
   OR EXISTS (SELECT 1 FROM tasks t JOIN calls c ON c.task_id = t.id WHERE t.agent_id = a.id)
ORDER BY a.created_at
"""


async def fetch() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(PER_CALL)
        calls = await cur.fetchall()
        await cur.execute(AGENTS)
        return calls, await cur.fetchall()


def percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def summarise(calls: list[dict[str, Any]], agents: list[dict[str, Any]], today: date) -> Analytics:
    ended = [c for c in calls if c["ended"]]
    durations = [c["duration_seconds"] for c in ended if c["duration_seconds"] is not None]
    days = [today - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]
    per_agent = []
    for agent in agents:
        mine = [c for c in calls if c["agent_id"] == agent["id"]]
        mine_ended = [c for c in mine if c["ended"]]
        per_agent.append(
            AgentStats(
                name=agent["name"],
                calls=len(mine),
                success_rate=percent(sum(c["success"] for c in mine_ended), len(mine_ended)),
            )
        )
    return Analytics(
        total_calls=len(calls),
        success_rate=percent(sum(c["success"] for c in ended), len(ended)),
        avg_duration_seconds=round(sum(durations) / len(durations), 1) if durations else 0.0,
        calls_by_day=[DayCalls(date=d.isoformat(), calls=sum(c["day"] == d for c in calls)) for d in days],
        agents=sorted(per_agent, key=lambda a: -a.calls),
    )


@router.get("/analytics/summary", response_model=Analytics)
async def analytics_summary() -> Analytics:
    calls, agents = await fetch()
    return summarise(calls, agents, today=datetime.now(UK).date())
