"""ElevenLabs server tools the voice agent calls mid-call. Owner: Alex.

POST /webhooks/elevenlabs/tools/request_payment_approval

The voice agent calls this when the business asks for a deposit. We create a pending_approval payment
(the approval card appears in the app), wait up to PAYMENT_WAIT_SECONDS for the user to approve or
decline, and answer with a `message` the voice agent should act on. Approval itself goes through
POST /payments/{id}/approve, which charges Stripe test mode.

Request (JSON; configure these in the ElevenLabs tool):
    call_id          our calls.id, passed to the agent by start_call as a dynamic variable (preferred)
    conversation_id  {{system__conversation_id}}, matched to calls.el_conversation_id (fallback)
    amount           deposit in pounds, e.g. 20 or 20.50 (the model says pounds more reliably than pence)
    currency         optional, default "GBP"
    description      optional, e.g. "Deposit for a table for 4"
Header: X-Tool-Secret: <ELEVENLABS_TOOL_SECRET>, required when that setting is set.

Response (always 200 for a known call, so the voice agent can read `message`):
    {"status": "approved" | "denied" | "pending" | "not_allowed" | "invalid", "payment_id": str | null,
     "message": str}
"""

import asyncio
import logging
import secrets
import time
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.orchestrator import store

log = logging.getLogger(__name__)
router = APIRouter(tags=["voice tools"])

MAX_DEPOSIT_PENCE = 50_000  # £500: anything bigger is almost certainly a mishearing
POLL_SECONDS = 1.0


class PaymentApprovalRequest(BaseModel):
    call_id: str | None = None
    conversation_id: str | None = None
    amount: Decimal | str = Field(description="Deposit in pounds, e.g. 20 or 20.50")
    currency: str = "GBP"
    description: str = ""


class PaymentApprovalResponse(BaseModel):
    status: str
    payment_id: str | None = None
    message: str


def pounds_to_pence(amount: Decimal | str) -> int | None:
    try:
        value = Decimal(str(amount).replace("£", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    pence = int((value * 100).to_integral_value())
    return pence if 0 < pence <= MAX_DEPOSIT_PENCE else None


def check_secret(request: Request, given: str | None) -> None:
    expected = request.app.state.settings.elevenlabs_tool_secret
    if expected and not secrets.compare_digest(given or "", expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad tool secret.")


async def wait_for_decision(payment_id: str, wait_seconds: float) -> str:
    deadline = time.monotonic() + wait_seconds
    while True:
        current = await store.payment_status(payment_id)
        if current != "pending_approval" or time.monotonic() >= deadline:
            return current
        await asyncio.sleep(POLL_SECONDS)


@router.post("/webhooks/elevenlabs/tools/request_payment_approval", response_model=PaymentApprovalResponse)
async def request_payment_approval(
    body: PaymentApprovalRequest, request: Request, x_tool_secret: str | None = Header(default=None)
) -> PaymentApprovalResponse:
    check_secret(request, x_tool_secret)

    call_id = body.call_id or (body.conversation_id and await store.find_call_by_conversation(body.conversation_id))
    if not call_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown call: pass call_id or conversation_id.")

    pence = pounds_to_pence(body.amount)
    if pence is None:
        return PaymentApprovalResponse(
            status="invalid",
            message="That amount doesn't look right. Ask the business to repeat the deposit amount in pounds.",
        )

    try:
        result = await store.request_payment(call_id, pence, body.currency.upper(), body.description.strip())
    except store.CallNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown call.") from None

    if result["outcome"] == "not_allowed":
        return PaymentApprovalResponse(
            status="not_allowed",
            message="You're not allowed to agree to payments for this user. Say they'll arrange any deposit directly.",
        )
    if result["outcome"] == "inactive":
        return PaymentApprovalResponse(status="invalid", message="This task has already finished.")

    payment = result["payment"]
    decision = await wait_for_decision(payment["id"], request.app.state.settings.payment_wait_seconds)
    log.info("payment %s for call %s: %s", payment["id"], call_id, decision)
    amount = f"£{payment['amount'] / 100:.2f}"
    if decision in ("approved", "paid"):
        return PaymentApprovalResponse(
            status="approved",
            payment_id=payment["id"],
            message=f"The user approved the {amount} deposit. Tell the business it's approved and confirm the booking.",
        )
    if decision == "denied":
        return PaymentApprovalResponse(
            status="denied",
            payment_id=payment["id"],
            message=f"The user declined the {amount} deposit. Don't agree to it; politely say they won't pay a deposit.",
        )
    return PaymentApprovalResponse(
        status="pending",
        payment_id=payment["id"],
        message="The user hasn't answered yet. Tell the business you'll confirm the deposit shortly, "
        "then call this tool again to check (it won't create a second request).",
    )
