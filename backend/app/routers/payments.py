"""Payment approval endpoints used by the UI's approval card. Owner: Alex."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.evan.models import Payment
from app.orchestrator import store
from app.tools.payments import ChargeFailed, charge

log = logging.getLogger(__name__)
router = APIRouter(tags=["payments"])


async def _decide(payment_id: str, approve: bool) -> dict:
    try:
        return await store.decide_payment(payment_id, approve)
    except store.PaymentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found.") from None
    except store.PaymentAlreadyDecided as e:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This payment is already {e.status.replace('_', ' ')}.") from None


@router.post("/payments/{payment_id}/approve", response_model=Payment)
async def approve_payment(payment_id: str) -> dict:
    """The user approved: charge it (Stripe test mode) and mark it paid."""
    payment = await _decide(payment_id, approve=True)
    try:
        stripe_pi_id = await charge(payment)
    except ChargeFailed as e:
        log.warning("Charge for payment %s failed: %s", payment_id, e)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Approved, but the test payment failed: {e} Try approving again."
        ) from None
    return await store.mark_paid(payment["id"], stripe_pi_id)


@router.post("/payments/{payment_id}/deny", response_model=Payment)
async def deny_payment(payment_id: str) -> dict:
    return await _decide(payment_id, approve=False)
