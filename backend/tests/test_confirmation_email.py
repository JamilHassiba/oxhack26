from app.services import confirmation_email

DETAILS = {
    "outcome": {
        "booked": True,
        "starts_at": "2026-10-26T19:00",
        "details": "Table for 2",
        "booking_name": "Alex",
        "venue": "The Ivy Oxford",
        "deposit_required": True,
        "deposit_amount_pence": 2000,
        "reason": "Table for 2 confirmed at 19:00 with a £20 deposit.",
    },
    "business_name": "The Ivy Oxford",
    "payment": {"amount": 2000, "currency": "GBP", "status": "paid"},
}


def test_rows_match_the_chat_result_table():
    assert confirmation_email.booking_rows(DETAILS) == [
        ("Result", "Confirmed"),
        ("Business", "The Ivy Oxford"),
        ("Date", "Monday 26 October"),
        ("Time", "7:00pm"),
        ("Details", "Table for 2"),
        ("Name", "Alex"),
        ("Deposit", "£20.00 · Paid"),
    ]


def test_unpaid_deposit_and_unbooked_calls():
    unpaid = {**DETAILS, "payment": None}
    assert ("Deposit", "£20.00 · Still to pay") in confirmation_email.booking_rows(unpaid)

    not_booked = {"outcome": {"booked": False, "starts_at": "2026-10-26T19:00", "venue": "The Ivy Oxford"}}
    assert confirmation_email.booking_rows(not_booked) == [("Result", "Not confirmed"), ("Business", "The Ivy Oxford")]


def test_render_escapes_what_gemini_wrote():
    html = confirmation_email.render(
        subject="Booked: The Ivy <Oxford>", body="Hi Alex,\n\nAll set & done.", agent_name="Maya", details=DETAILS
    )
    assert "The Ivy &lt;Oxford&gt;" in html and "<Oxford>" not in html
    assert "All set &amp; done." in html
    assert "Monday 26 October" in html and "7:00pm" in html and "£20.00 · Paid" in html
    assert "Booked for you by Maya" in html
