"""Database reads/writes for the orchestrator (plain SQL). Tables come from Jamil's migrations/001_init.sql."""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app import db
from app.contracts import TaskStatus

ACTIVE_STATUSES = [TaskStatus.PLANNING, TaskStatus.CALLING, TaskStatus.AWAITING_APPROVAL]


class AgentNotFound(Exception):
    pass


class AgentBusy(Exception):
    """The agent already has a task running (the chat box is locked until it finishes)."""


async def create_task(agent_id: str, message: str) -> str:
    """Saves the user's message and a new `planning` task for it. Returns the task id."""
    try:
        UUID(agent_id)
    except ValueError:
        raise AgentNotFound(agent_id) from None

    async with db.get_pool().connection() as conn, conn.transaction():
        # Lock the agent row so two quick messages can't both start a task.
        agent = await (await conn.execute("SELECT id FROM agents WHERE id = %s AND archived_at IS NULL FOR UPDATE", (agent_id,))).fetchone()
        if agent is None:
            raise AgentNotFound(agent_id)
        busy = await (
            await conn.execute(
                "SELECT 1 FROM tasks WHERE agent_id = %s AND status = ANY(%s) LIMIT 1",
                (agent_id, ACTIVE_STATUSES),
            )
        ).fetchone()
        if busy:
            raise AgentBusy(agent_id)

        (task_id,) = await (
            await conn.execute("INSERT INTO tasks (agent_id, goal) VALUES (%s, %s) RETURNING id", (agent_id, message))
        ).fetchone()
        await conn.execute(
            "INSERT INTO messages (agent_id, task_id, role, content) VALUES (%s, %s, 'user', %s)",
            (agent_id, task_id, message),
        )
    return str(task_id)


async def load_task(task_id: str) -> dict[str, Any]:
    """The task plus what the orchestrator needs about its agent and user."""
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """
            SELECT t.id::text AS id, t.goal, t.status,
                   a.id::text AS agent_id, a.name AS agent_name, a.persona, a.tools,
                   u.name AS user_name
            FROM tasks t
            JOIN agents a ON a.id = t.agent_id
            JOIN users u ON u.id = a.user_id
            WHERE t.id = %s
            """,
            (task_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise LookupError(f"Task {task_id} not found")
    return row


async def finish_task(task_id: str, status: TaskStatus, summary: str) -> None:
    """Sets the task's final status and summary, and adds the summary to the chat as the agent's reply."""
    async with db.get_pool().connection() as conn, conn.transaction():
        await conn.execute(
            "UPDATE tasks SET status = %s, summary = %s, updated_at = now() WHERE id = %s",
            (status, summary, task_id),
        )
        await conn.execute(
            "INSERT INTO messages (agent_id, task_id, role, content)"
            " SELECT agent_id, id, 'assistant', %s FROM tasks WHERE id = %s",
            (summary, task_id),
        )


async def set_task_status(task_id: str, status: TaskStatus) -> None:
    async with db.get_pool().connection() as conn:
        await conn.execute("UPDATE tasks SET status = %s, updated_at = now() WHERE id = %s", (status, task_id))


async def find_contacts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Contacts whose name contains `query` (case-insensitive). Phone numbers are left out on purpose."""
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT id::text AS contact_id, name, notes FROM contacts WHERE name ILIKE %s ORDER BY name LIMIT %s",
            (f"%{query.strip()}%", limit),
        )
        return await cur.fetchall()


async def list_contact_names() -> list[str]:
    async with db.get_pool().connection() as conn:
        return [row[0] for row in await (await conn.execute("SELECT name FROM contacts ORDER BY name")).fetchall()]


async def get_contact(contact_id: str) -> dict[str, Any] | None:
    try:
        UUID(contact_id)
    except ValueError:
        return None
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT id::text AS id, name, phone FROM contacts WHERE id = %s", (contact_id,))
        return await cur.fetchone()


async def count_calls(task_id: str) -> int:
    async with db.get_pool().connection() as conn:
        (n,) = await (await conn.execute("SELECT count(*) FROM calls WHERE task_id = %s", (task_id,))).fetchone()
    return n
