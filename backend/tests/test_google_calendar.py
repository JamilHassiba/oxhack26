import asyncio

import pytest

from app.config import Settings
from app.services import google_calendar

EVENT = {
    "id": "0f8e2a1c-3b4d-4e5f-9a6b-7c8d9e0f1a2b",
    "task_id": "task-1",
    "title": "Dinner at The Ivy Oxford (table for 2)",
    "starts_at": "2026-10-26T19:00:00+00:00",
    "ends_at": "2026-10-26T20:30:00+00:00",
    "location": "",
}
TASK = {"id": "task-1", "agent_name": "Maya", "user_name": "Alex"}
DETAILS = {
    "outcome": {
        "booked": True,
        "booking_name": "Alex",
        "party_size": 2,
        "venue": "The Ivy Oxford",
        "deposit_required": True,
        "deposit_amount_pence": 2000,
        "reason": "Table for 2 confirmed at 19:00 with a £20 deposit.",
    },
    "phone": "+441865000000",
    "contact_name": "The Ivy Oxford",
    "payment": {"amount": 2000, "currency": "GBP", "status": "paid"},
}
CONNECTED = Settings(_env_file=None, google_service_account_file="key.json", google_calendar_id="alex@gmail.com")


def test_event_has_the_booking_details():
    body = google_calendar.event_body(EVENT, TASK, DETAILS)

    assert body["id"] == "0f8e2a1c3b4d4e5f9a6b7c8d9e0f1a2b"  # Google ids: no dashes
    assert body["summary"] == "Dinner at The Ivy Oxford (table for 2)"
    assert body["location"] == "The Ivy Oxford"  # falls back to the venue when Gemini gave no location
    assert body["start"] == {"dateTime": "2026-10-26T19:00:00+00:00", "timeZone": "Europe/London"}
    assert body["description"].splitlines() == [
        "Name on booking: Alex",
        "Party size: 2",
        "Deposit: £20.00 (paid)",
        "The Ivy Oxford: +441865000000",
        "",
        "Booked by Maya, your AI concierge, on a phone call.",
        "Table for 2 confirmed at 19:00 with a £20 deposit.",
    ]


def test_unpaid_deposit_and_no_deposit_are_spelled_out():
    unpaid = {**DETAILS, "payment": None}
    assert "Deposit: £20.00 (still to pay)" in google_calendar.event_body(EVENT, TASK, unpaid)["description"]

    none = {**DETAILS, "payment": None, "outcome": {**DETAILS["outcome"], "deposit_required": False}}
    assert "Deposit: none" in google_calendar.event_body(EVENT, TASK, none)["description"]


@pytest.fixture
def google(monkeypatch):
    w = {"settings": CONNECTED, "inserted": [], "error": None}

    async def booking_details(task_id):
        return DETAILS

    async def insert(body):
        if w["error"]:
            raise w["error"]
        w["inserted"].append(body)

    monkeypatch.setattr(google_calendar, "get_settings", lambda: w["settings"])
    monkeypatch.setattr(google_calendar, "booking_details", booking_details)
    monkeypatch.setattr(google_calendar, "_insert", insert)
    return w


def test_adds_the_event_when_connected(google):
    assert asyncio.run(google_calendar.add_event(EVENT, TASK)) == "added"
    assert google["inserted"][0]["summary"] == EVENT["title"]


def test_does_nothing_when_not_connected(google):
    google["settings"] = Settings(_env_file=None)

    assert asyncio.run(google_calendar.add_event(EVENT, TASK)) == "not_connected"
    assert google["inserted"] == []


def test_google_failure_does_not_break_the_booking(google):
    google["error"] = RuntimeError("Google said 403: calendar not shared with the service account")

    assert asyncio.run(google_calendar.add_event(EVENT, TASK)) == "failed"
