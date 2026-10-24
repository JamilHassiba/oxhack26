"""Payments via Stripe test mode, always behind user approval. Owner: Alex.

The charge runs only after the user approves in the app (routers/payments.py). Only Stripe *test* keys
(sk_test_...) are accepted, so no real money can ever move. With no key set, a stand-in marks the
payment as paid without contacting Stripe.
"""

import logging
from typing import Any

import stripe

from app.config import get_settings

log = logging.getLogger(__name__)

TEST_CARD = "pm_card_visa"  # Stripe's built-in test Visa card


class ChargeFailed(Exception):
    pass


async def charge(payment: dict[str, Any]) -> str:
    """Charges an approved payment in Stripe test mode and returns the PaymentIntent id."""
    key = get_settings().stripe_secret_key
    if not key:
        log.warning("STRIPE_SECRET_KEY not set: payment %s simulated, nothing charged", payment["id"])
        return f"simulated_{payment['id']}"
    if not key.startswith(("sk_test_", "rk_test_")):
        raise ChargeFailed("Only Stripe test keys (sk_test_...) are allowed, so no real money can move.")

    client = stripe.StripeClient(key, http_client=stripe.HTTPXClient())
    try:
        intent = await client.v1.payment_intents.create_async(
            params={
                "amount": payment["amount"],
                "currency": payment["currency"].lower(),
                "payment_method": TEST_CARD,
                "confirm": True,
                "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
                "description": payment["description"] or f"Deposit: {payment['merchant'] or 'booking'}",
                "metadata": {"payment_id": payment["id"], "task_id": payment["task_id"]},
            },
            # Approving twice (e.g. retry after an error) can never charge twice.
            options={"idempotency_key": f"payment-{payment['id']}"},
        )
    except stripe.StripeError as e:
        raise ChargeFailed(e.user_message or str(e)) from e
    if intent.status != "succeeded":
        raise ChargeFailed(f"Stripe payment status is {intent.status}")
    return intent.id
