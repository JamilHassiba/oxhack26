"""Evan's confirmation-email tool. Recipients come from the task's owning user."""

import hashlib
import json
from uuid import UUID
import httpx
from fastapi import HTTPException
from app.evan.database import connection
from app.evan.repository import Repository
from app.evan.settings import get_settings


async def send_email(*, task_id: str, subject: str, body: str) -> dict:
    """Send one plain-text confirmation via Resend. Same-task retries are idempotent."""
    task_uuid = UUID(task_id)
    if (
        not subject.strip()
        or len(subject) > 200
        or "\r" in subject
        or "\n" in subject
        or not body.strip()
        or len(body) > 20000
    ):
        raise ValueError(
            "Supply a single-line subject (1–200 characters) and body (1–20000)."
        )
    settings = get_settings()
    if (
        not settings.resend_api_key.get_secret_value()
        or not settings.email_from
        or "\r" in settings.email_from
        or "\n" in settings.email_from
    ):
        raise HTTPException(
            503, "Configure RESEND_API_KEY and EMAIL_FROM before sending email."
        )
    async with connection() as conn:
        repo = Repository(conn)
        owner = await repo.tool_owner(task_uuid, "email")
        recipient = owner["email"]
        if (
            not recipient
            or "@" not in recipient
            or "\r" in recipient
            or "\n" in recipient
        ):
            raise ValueError("The task owner needs a valid email address.")
        payload = {
            "from": settings.email_from,
            "to": [recipient],
            "subject": subject.strip(),
            "text": body,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 1))", (str(task_uuid),)
        )
        previous = await repo.one(
            "SELECT provider_id, fingerprint FROM email_deliveries WHERE task_id = %s",
            (task_uuid,),
        )
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise HTTPException(
                    409, "This task already sent a different confirmation email."
                )
            return {"id": previous["provider_id"], "status": "sent"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                        "Idempotency-Key": f"concierge-confirmation/{task_uuid}",
                    },
                )
            response.raise_for_status()
            provider_id = response.json()["id"]
            if not isinstance(provider_id, str) or not provider_id:
                raise ValueError("Invalid provider response")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # Never echo provider errors or credentials into a tool result or API response.
            raise HTTPException(
                502, "Email provider did not confirm delivery. Retry this same task."
            ) from exc
        await conn.execute(
            "INSERT INTO email_deliveries (task_id, provider_id, fingerprint) VALUES (%s, %s, %s)",
            (task_uuid, provider_id, fingerprint),
        )
        return {"id": provider_id, "status": "sent"}
