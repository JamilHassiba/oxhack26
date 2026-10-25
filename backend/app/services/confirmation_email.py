"""The styled HTML version of the booking confirmation email. Owner: Alex.

Gemini still writes the subject and the plain-text message; this wraps them in a card with the booking
facts from the call's outcome and the task's deposit (the same rows as the chat's result table), so the
facts in the email always match what was actually agreed on the call.
"""

from datetime import datetime
from html import escape
from typing import Any

ACCENT = "#a34125"
PAYMENT_STATUS = {
    "pending_approval": "Awaiting your approval",
    "approved": "Approved",
    "paid": "Paid",
    "denied": "Declined",
}


def uk_wall_clock(value: str) -> tuple[str, str]:
    """"2026-10-26T18:30" (UK time, no offset) -> ("Monday 26 October", "6:30pm")."""
    when = datetime.fromisoformat(value)
    hour = when.hour % 12 or 12
    return f"{when:%A} {when.day} {when:%B}", f"{hour}:{when.minute:02d}{'am' if when.hour < 12 else 'pm'}"


def booking_rows(details: dict[str, Any]) -> list[tuple[str, str]]:
    outcome = details.get("outcome") or {}
    payment = details.get("payment")
    booked = bool(outcome.get("booked"))
    date, time = uk_wall_clock(outcome["starts_at"]) if outcome.get("starts_at") else (None, None)
    if payment:
        deposit = f"£{payment['amount'] / 100:.2f} · {PAYMENT_STATUS.get(payment['status'], payment['status'])}"
    elif outcome.get("deposit_required") and outcome.get("deposit_amount_pence"):
        deposit = f"£{outcome['deposit_amount_pence'] / 100:.2f} · Still to pay"
    else:
        deposit = None
    rows = [
        ("Result", "Confirmed" if booked else "Not confirmed"),
        ("Business", outcome.get("venue") or details.get("business_name")),
        ("Date", date if booked else None),
        ("Time", time if booked else None),
        ("Details", outcome.get("details")),
        ("Name", outcome.get("booking_name") if booked else None),
        ("Deposit", deposit),
    ]
    return [(label, value) for label, value in rows if value]


def render(*, subject: str, body: str, agent_name: str, details: dict[str, Any]) -> str:
    rows = "".join(
        f'<tr><td style="padding:10px 0;color:#6b7563;border-top:1px solid #e3e8dc;width:38%">{escape(label)}</td>'
        f'<td style="padding:10px 0;color:#1f2a17;border-top:1px solid #e3e8dc;font-weight:600">{escape(value)}</td></tr>'
        for label, value in booking_rows(details)
    )
    message = "".join(f'<p style="margin:0 0 12px">{escape(p)}</p>' for p in body.split("\n\n") if p.strip())
    reason = (details.get("outcome") or {}).get("reason")
    return f"""<!doctype html>
<html><body style="margin:0;padding:24px 12px;background:#f5f6f1;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2a17">
<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #d8dfcc;border-radius:12px;overflow:hidden">
  <div style="padding:20px 24px;background:{ACCENT};color:#fff">
    <div style="font-size:13px;opacity:.85">concierge.</div>
    <div style="font-size:20px;font-weight:700;margin-top:4px">{escape(subject)}</div>
  </div>
  <div style="padding:20px 24px">
    <div style="font-size:15px;line-height:1.5">{message}</div>
    {f'<table style="width:100%;border-collapse:collapse;font-size:14px;margin-top:8px">{rows}</table>' if rows else ""}
    {f'<p style="margin:16px 0 0;font-size:13px;color:#6b7563">On the call: {escape(reason)}</p>' if reason else ""}
  </div>
  <div style="padding:14px 24px;background:#f0f3ea;font-size:12px;color:#6b7563">
    Booked for you by {escape(agent_name)}, your AI concierge, on a phone call.
  </div>
</div>
</body></html>"""
