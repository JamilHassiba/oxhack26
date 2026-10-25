"""Parameterized SQL against the agreed schema. Owns no shared DB setup or migration runner."""

from uuid import UUID, uuid4
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app.evan.models import (
    Agent,
    AgentInput,
    AgentPatch,
    Task,
)

ACTIVE = ("planning", "calling", "awaiting_approval")
AGENT_COLUMNS = "id, name, tools"
# Lateral subqueries avoid multiplying rows when a task has several calls/events.
TASK_SELECT = """
SELECT t.id, t.agent_id, t.goal, t.status, t.summary, t.created_at,
       row_to_json(c) AS call, row_to_json(p) AS payment,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('ts', e.ts, 'call_id', e.call_id,
           'kind', e.kind, 'payload', e.payload) ORDER BY e.ts)
           FROM call_events e WHERE e.call_id = c.id), '[]'::jsonb) AS events
FROM tasks t
LEFT JOIN LATERAL (SELECT * FROM calls WHERE task_id = t.id
    ORDER BY started_at DESC NULLS LAST, id DESC LIMIT 1) c ON true
LEFT JOIN LATERAL (SELECT * FROM payments WHERE task_id = t.id
    ORDER BY (status = 'pending_approval') DESC, id DESC LIMIT 1) p ON true
"""


def wire(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [wire(item) for item in value]
    return value


class Repository:
    def __init__(self, conn):
        self.conn = conn

    async def rows(self, query, params=()):
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchall()

    async def one(self, query, params=()):
        rows = await self.rows(query, params)
        return rows[0] if rows else None

    async def agents(self):
        return [
            Agent.model_validate(wire(row))
            for row in await self.rows(
                f"SELECT {AGENT_COLUMNS} FROM agents WHERE archived_at IS NULL ORDER BY created_at, id"
            )
        ]

    async def agent(self, agent_id, lock=False):
        row = await self.one(
            f"SELECT {AGENT_COLUMNS} FROM agents WHERE id = %s AND archived_at IS NULL"
            + (" FOR UPDATE" if lock else ""),
            (agent_id,),
        )
        if not row:
            raise HTTPException(404, "Agent not found.")
        return Agent.model_validate(wire(row))

    async def create_agent(self, data: AgentInput):
        user = await self.one("SELECT id FROM users ORDER BY id LIMIT 1")
        if not user:
            raise HTTPException(503, "Seed the demo user before creating an agent.")
        row = await self.one(
            f"INSERT INTO agents (id, user_id, name, tools) VALUES (%s, %s, %s, %s) RETURNING {AGENT_COLUMNS}",
            (uuid4(), user["id"], data.name, Jsonb(data.tools)),
        )
        return Agent.model_validate(wire(row))

    async def update_agent(self, agent_id, data: AgentPatch):
        await self.agent(agent_id, lock=True)
        values = data.model_dump(exclude_unset=True)
        # Keys come only from the extra-forbid Pydantic model, never user SQL text.
        assignments = ", ".join(f"{key} = %s" for key in values)
        params = [
            Jsonb(value) if key == "tools" else value for key, value in values.items()
        ]
        row = await self.one(
            f"UPDATE agents SET {assignments} WHERE id = %s RETURNING {AGENT_COLUMNS}",
            (*params, agent_id),
        )
        return Agent.model_validate(wire(row))

    async def delete_agent(self, agent_id):
        await self.agent(agent_id, lock=True)
        active = await self.one(
            "SELECT id FROM tasks WHERE agent_id = %s AND status = ANY(%s) LIMIT 1",
            (agent_id, list(ACTIVE)),
        )
        if active:
            raise HTTPException(
                409,
                "Finish active tasks and payment approvals before deleting this agent.",
            )
        await self.conn.execute(
            "UPDATE agents SET archived_at = now() WHERE id = %s", (agent_id,)
        )

    async def task(self, task_id):
        row = await self.one(TASK_SELECT + " WHERE t.id = %s", (task_id,))
        if not row:
            raise HTTPException(404, "Task not found.")
        if row.get("call") and row["call"].get("transcript") is None:
            row["call"]["transcript"] = []
        return Task.model_validate(wire(row))

    async def tasks(self, agent_id):
        # Archived agents retain readable history through their stable IDs.
        exists = await self.one("SELECT id FROM agents WHERE id = %s", (agent_id,))
        if not exists:
            raise HTTPException(404, "Agent not found.")
        rows = await self.rows(
            TASK_SELECT + " WHERE t.agent_id = %s ORDER BY t.created_at, t.id",
            (agent_id,),
        )
        for row in rows:
            if row.get("call") and row["call"].get("transcript") is None:
                row["call"]["transcript"] = []
        return [Task.model_validate(wire(row)) for row in rows]

    async def tool_owner(self, task_id, tool):
        row = await self.one(
            "SELECT a.tools, u.email FROM tasks t JOIN agents a ON a.id = t.agent_id JOIN users u ON u.id = a.user_id WHERE t.id = %s FOR SHARE OF a",
            (task_id,),
        )
        if not row:
            raise HTTPException(404, "Task not found.")
        if tool not in row["tools"]:
            raise HTTPException(403, f"The agent does not have {tool} permission.")
        return row

