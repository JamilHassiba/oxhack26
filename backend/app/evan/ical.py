"""RFC 5545 text escaping, CRLF endings and UTF-8-safe 75-octet line folding."""

from datetime import datetime, timezone


def escape(value):
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def stamp(value):
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fold(line):
    pieces = []
    current = ""
    for character in line:
        if len((current + character).encode("utf-8")) > 75:
            pieces.append(current)
            current = " "
        current += character
    pieces.append(current)
    return "\r\n".join(pieces)


def calendar_feed(events):
    now = stamp(datetime.now(timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OxHack Concierge//EN",
        "CALSCALE:GREGORIAN",
    ]
    for event in events:
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event.id}@concierge",
                f"DTSTAMP:{now}",
                f"DTSTART:{stamp(event.starts_at)}",
                f"DTEND:{stamp(event.ends_at)}",
                f"SUMMARY:{escape(event.title)}",
                f"LOCATION:{escape(event.location)}",
                "END:VEVENT",
            ]
        )
    lines.extend(["END:VCALENDAR", ""])
    return "\r\n".join(fold(line) for line in lines)
