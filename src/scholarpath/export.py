"""Exporting the saved list: CSV and an ICS calendar file (G157).

Two formats, both honest about where the information came from:

- **CSV** - one row per saved record, with the deadline text **exactly as the
  page wrote it**, the source URL, and the date the page was last verified.
- **ICS** - a calendar file with one all-day event per record that has a
  readable deadline. A record without one gets no event: a calendar entry
  would need a date, and there is none.

Nothing is invented on the way out. A field the page never stated is empty in
the export, too.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Iterable

#: The columns of the CSV, in order.
CSV_COLUMNS = (
    "Title",
    "Provider",
    "Country",
    "Level",
    "Funding",
    "Amount",
    "Deadline (as written on the page)",
    "Deadline date",
    "Source URL",
    "Last verified",
    "Warning signs",
)

#: The producer written into the calendar file.
PRODID = "-//ScholarPath AI//Saved Opportunities//EN"


def _data(record: dict) -> dict:
    data = record.get("data")
    return data if isinstance(data, dict) else {}


def _values(record: dict) -> dict:
    values = _data(record).get("values")
    return dict(values) if isinstance(values, dict) else {}


def _warning_count(record: dict) -> int:
    signs = _data(record).get("warning_signs")
    if isinstance(signs, list):
        return len(signs)
    return 0


def export_row(record: dict) -> dict[str, str]:
    """One row of the CSV: what the page says, where it came from, when."""
    values = _values(record)
    deadline_text = str(record.get("deadline_text") or values.get("deadline") or "")
    retrieved = str(record.get("retrieved_at") or "")[:10]
    checked = str(_data(record).get("last_checked_at") or "")[:10]
    return {
        "Title": str(record.get("title") or values.get("title") or ""),
        "Provider": str(record.get("provider") or record.get("provider_domain") or ""),
        "Country": str(record.get("countries") or values.get("host_country") or ""),
        "Level": str(record.get("level") or values.get("degree_levels") or ""),
        "Funding": str(record.get("funding_type") or values.get("funding_coverage") or ""),
        "Amount": str(record.get("amount_text") or values.get("stipend") or ""),
        "Deadline (as written on the page)": deadline_text,
        "Deadline date": str(record.get("deadline_date") or ""),
        "Source URL": str(record.get("final_url") or record.get("requested_url") or ""),
        "Last verified": checked or retrieved,
        "Warning signs": str(_warning_count(record)),
    }


def csv_text(records: Iterable[dict]) -> str:
    """The saved list as CSV text (line endings are the CSV standard's)."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(CSV_COLUMNS), lineterminator="\r\n")
    writer.writeheader()
    for record in records:
        writer.writerow(export_row(record))
    return buffer.getvalue()


def _escape(text: str) -> str:
    """Escape a value for a calendar file, as RFC 5545 asks."""
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str, limit: int = 75) -> str:
    """Fold a long line, as the calendar format asks (75 octets)."""
    raw = line.encode("utf-8")
    if len(raw) <= limit:
        return line
    chunks: list[str] = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > limit - 1:
            chunks.append(current)
            current = " " + char
        else:
            current += char
    if current:
        chunks.append(current)
    return "\r\n".join(chunks)


def _stamp(moment: datetime | None = None) -> str:
    value = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%SZ")


def _date_value(value: str) -> str:
    return str(value or "").replace("-", "")


def ics_text(records: Iterable[dict], now: datetime | None = None) -> str:
    """The saved list as a calendar file.

    Only records with a readable deadline become events; the rest are left
    out, because an event needs a day and there is none.
    """
    stamp = _stamp(now)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for record in records:
        deadline = str(record.get("deadline_date") or "").strip()
        if not deadline:
            continue
        values = _values(record)
        title = str(record.get("title") or values.get("title") or "Saved scholarship")
        deadline_text = str(record.get("deadline_text") or values.get("deadline") or "")
        url = str(record.get("final_url") or record.get("requested_url") or "")
        record_id = int(record.get("id") or 0)
        description = "Deadline as written on the page: " + (deadline_text or "(none)")
        if url:
            description += f"\nSource: {url}"
        verified = str(record.get("retrieved_at") or "")[:10]
        if verified:
            description += f"\nLast verified: {verified}"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{record_id}-{_date_value(deadline)}@scholarpath",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{_date_value(deadline)}",
                f"DTEND;VALUE=DATE:{_date_value(deadline)}",
                f"SUMMARY:{_escape(title)}",
                f"DESCRIPTION:{_escape(description)}",
                f"URL:{_escape(url)}",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def ics_event_count(records: Iterable[dict]) -> int:
    """How many of the records have a readable deadline (and so an event)."""
    return sum(1 for record in records if str(record.get("deadline_date") or "").strip())
