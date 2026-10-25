from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from app.tools.email import send_email
from app.evan.settings import EvanSettings
from test_api import create, seed_task


@pytest.mark.asyncio
async def test_email_recipient_permission_idempotence_and_provider_errors(
    client, database, monkeypatch
):
    agent = create(client)
    task = seed_task(database, agent["id"])
    monkeypatch.setattr(
        "app.tools.email.get_settings",
        lambda: EvanSettings(
            resend_api_key="test-key",
            email_from="Concierge <bookings@example.com>",
            _env_file=None,
        ),
    )
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url == "https://api.resend.com/emails"
        assert request.headers["Idempotency-Key"] == f"concierge-confirmation/{task}"
        assert b"demo@example.com" in request.content
        return httpx.Response(200, json={"id": "provider-1"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.tools.email.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    args = dict(
        task_id=task, subject="Booking confirmed", body="Table for four at six."
    )
    assert await send_email(**args) == {"id": "provider-1", "status": "sent"}
    assert await send_email(**args) == {"id": "provider-1", "status": "sent"}
    assert len(calls) == 1
    with pytest.raises(HTTPException) as changed:
        await send_email(**{**args, "body": "Different message"})
    assert changed.value.status_code == 409
    client.patch("/agents/" + agent["id"], json={"tools": []})
    with pytest.raises(HTTPException) as forbidden:
        await send_email(**args)
    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_email_not_configured_and_header_injection(monkeypatch):
    monkeypatch.setattr(
        "app.tools.email.get_settings", lambda: EvanSettings(_env_file=None)
    )
    with pytest.raises(HTTPException) as missing:
        await send_email(task_id=str(uuid4()), subject="Test", body="Body")
    assert missing.value.status_code == 503
    with pytest.raises(ValueError):
        await send_email(
            task_id=str(uuid4()),
            subject="Subject\r\nBcc: evil@example.com",
            body="Body",
        )


@pytest.mark.asyncio
async def test_email_provider_failure_can_retry_without_leaking_provider_details(
    client, database, monkeypatch
):
    agent = create(client)
    task = seed_task(database, agent["id"])
    monkeypatch.setattr(
        "app.tools.email.get_settings",
        lambda: EvanSettings(
            resend_api_key="private-key",
            email_from="bookings@example.com",
            _env_file=None,
        ),
    )
    healthy = False
    keys = []

    def handle(request):
        keys.append(request.headers["Idempotency-Key"])
        return (
            httpx.Response(200, json={"id": "retry-ok"})
            if healthy
            else httpx.Response(500, text="private provider diagnostic")
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.tools.email.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    args = dict(task_id=task, subject="Confirmed", body="Dinner at six")
    with pytest.raises(HTTPException) as failure:
        await send_email(**args)
    assert failure.value.status_code == 502
    assert "private" not in failure.value.detail
    with database[1]() as conn:
        assert conn.execute("SELECT count(*) FROM email_deliveries").fetchone()[0] == 0
    healthy = True
    assert (await send_email(**args))["id"] == "retry-ok"
    assert len(set(keys)) == 1
