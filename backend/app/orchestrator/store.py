"""Database reads/writes for the orchestrator (plain SQL). Tables come from Jamil's migrations/001_init.sql."""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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


async def load_call(call_id: str) -> dict[str, Any]:
    """The call row Jamil's webhook filled in, plus the name of the contact that was called."""
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """
            SELECT c.id::text AS id, c.task_id::text AS task_id, c.to_number, c.status,
                   c.transcript, c.summary, c.outcome,
                   (SELECT name FROM contacts WHERE phone = c.to_number ORDER BY created_at LIMIT 1) AS contact_name
            FROM calls c
            WHERE c.id = %s
            """,
            (call_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise LookupError(f"Call {call_id} not found")
    return row


async def save_call_outcome(call_id: str, outcome: dict[str, Any]) -> None:
    """Stores our extracted outcome, unless Jamil's webhook already stored one."""
    async with db.get_pool().connection() as conn:
        await conn.execute(
            "UPDATE calls SET outcome = %s WHERE id = %s AND outcome IS NULL", (Jsonb(outcome), call_id)
        )


PAYMENT_COLUMNS = (
    "id::text AS id, task_id::text AS task_id, amount, currency, merchant, description, status, stripe_pi_id"
)


class PaymentNotFound(Exception):
    pass


class PaymentAlreadyDecided(Exception):
    def __init__(self, status: str):
        super().__init__(status)
        self.status = status


async def decide_payment(payment_id: str, approve: bool) -> dict[str, Any]:
    """pending_approval -> approved / denied, atomically so a double click can't decide twice.

    Approving an already-approved payment is allowed: that retries a charge that failed earlier.
    Then, if the task was waiting on this decision, it goes back to `calling` (the voice agent carries on).
    """
    try:
        UUID(payment_id)
    except ValueError:
        raise PaymentNotFound(payment_id) from None
    allowed_from = ["pending_approval", "approved"] if approve else ["pending_approval"]
    async with db.get_pool().connection() as conn, conn.transaction():
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"UPDATE payments SET status = %s, updated_at = now() WHERE id = %s AND status = ANY(%s)"
            f" RETURNING {PAYMENT_COLUMNS}",
            ("approved" if approve else "denied", payment_id, allowed_from),
        )
        payment = await cur.fetchone()
        if payment is None:
            existing = await (await conn.execute("SELECT status FROM payments WHERE id = %s", (payment_id,))).fetchone()
            if existing is None:
                raise PaymentNotFound(payment_id)
            raise PaymentAlreadyDecided(existing[0])
        await conn.execute(
            "UPDATE tasks SET status = %s, updated_at = now() WHERE id = %s AND status = %s",
            (TaskStatus.CALLING, payment["task_id"], TaskStatus.AWAITING_APPROVAL),
        )
    return payment


async def mark_paid(payment_id: str, stripe_pi_id: str) -> dict[str, Any]:
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"UPDATE payments SET status = 'paid', stripe_pi_id = %s, updated_at = now() WHERE id = %s"
            f" RETURNING {PAYMENT_COLUMNS}",
            (stripe_pi_id, payment_id),
        )
        return await cur.fetchone()


async def task_payments(task_id: str) -> list[dict[str, Any]]:
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"SELECT {PAYMENT_COLUMNS} FROM payments WHERE task_id = %s ORDER BY created_at", (task_id,)
        )
        return await cur.fetchall()


async def recent_tasks(agent_id: str, before_task_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """The agent's last few finished tasks before this one, oldest first: context for follow-up messages."""
    async with db.get_pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """
            SELECT goal, status, summary FROM (
                SELECT goal, status, summary, created_at FROM tasks
                WHERE agent_id = %s AND id <> %s AND status IN ('done', 'failed') AND summary IS NOT NULL
                  AND created_at <= (SELECT created_at FROM tasks WHERE id = %s)
                ORDER BY created_at DESC LIMIT %s
            ) recent
            ORDER BY created_at
            """,
            (agent_id, before_task_id, before_task_id, limit),
        )
        return await cur.fetchall()
