"""The styled HTML version of the booking confirmation email. Owner: Alex.

Gemini still writes the subject and the plain-text message; this wraps them in a card with the booking
facts from the call's outcome and the task's deposit, so the facts always match what was agreed on the call.
booking_rows mirrors bookingRows in frontend/src/components/BookingSummary.tsx row for row: keep them in step.
"""

from datetime import datetime
from html import escape
from typing import Any

ACCENT = "#4351c4"
PAYMENT_STATUS = {
    "pending_approval": "Awaiting your approval",
    "approved": "Approved",
    "paid": "Paid",
    "denied": "Declined",
}


def uk_wall_clock(value: str) -> tuple[str, str]:
    """"2026-10-26T18:30" (UK time, no offset) -> ("Mon 26 Oct", "18:30"), as the chat shows it."""
    when = datetime.fromisoformat(value)
    return f"{when:%a} {when.day} {when:%b}", f"{when:%H:%M}"


def booking_rows(details: dict[str, Any]) -> list[tuple[str, str]]:
    outcome = details.get("outcome") or {}
    payment = details.get("payment")
    booked = bool(outcome.get("booked"))
    date, time = uk_wall_clock(outcome["starts_at"]) if outcome.get("starts_at") else (None, None)
    if payment:
        deposit = f"£{payment['amount'] / 100:,.2f} · {PAYMENT_STATUS.get(payment['status'], payment['status'])}"
    elif outcome.get("deposit_required") and outcome.get("deposit_amount_pence"):
        deposit = f"£{outcome['deposit_amount_pence'] / 100:,.2f} · Still to pay"
    else:
        deposit = None
    offered = outcome.get("offered_times") or []
    rows = [
        ("Result", "Confirmed" if booked else "Not confirmed"),
        ("Business", outcome.get("venue") or (payment or {}).get("merchant")),
        ("Date", date if booked else None),
        ("Time", time if booked else None),
        ("Details", outcome.get("details")),
        ("Name", outcome.get("booking_name") if booked else None),
        ("Deposit", deposit),
        ("Other times offered", ", ".join(uk_wall_clock(t)[1] for t in offered) if not booked and offered else None),
    ]
    return [(label, value) for label, value in rows if value]


def render(*, subject: str, body: str, agent_name: str, details: dict[str, Any]) -> str:
    rows = "".join(
        f'<tr><td style="padding:10px 0;color:#63636b;border-top:1px solid #e4e4e7;width:38%">{escape(label)}</td>'
        f'<td style="padding:10px 0;color:#18181b;border-top:1px solid #e4e4e7;font-weight:600">{escape(value)}</td></tr>'
        for label, value in booking_rows(details)
    )
    message = "".join(f'<p style="margin:0 0 12px">{escape(p)}</p>' for p in body.split("\n\n") if p.strip())
    return f"""<!doctype html>
<html><body style="margin:0;padding:24px 12px;background:#f7f7f8;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#18181b">
<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e4e4e7;border-radius:12px;overflow:hidden">
  <div style="padding:20px 24px;background:{ACCENT};color:#fff">
    <div style="font-size:13px;opacity:.85">Smart Connect</div>
    <div style="font-size:20px;font-weight:700;margin-top:4px">{escape(subject)}</div>
  </div>
  <div style="padding:20px 24px">
    <div style="font-size:15px;line-height:1.5">{message}</div>
    {f'<table style="width:100%;border-collapse:collapse;font-size:14px;margin-top:8px">{rows}</table>' if rows else ""}  </div>
  <div style="padding:14px 24px;background:#f4f4f5;font-size:12px;color:#63636b">
    Booked for you by {escape(agent_name)}, your AI concierge, on a phone call.
  </div>
</div>
</body></html>"""
