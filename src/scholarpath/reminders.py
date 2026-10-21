"""Deadline reminders: a local Windows notification, opt-in (G156).

A reminder is due when a saved record's deadline is exactly 30, 14, 7 or 1 day
away. The rule is deliberately plain:

- only a **saved** record is reminded about;
- only a record with a stored, unambiguous ``deadline_date`` is reminded about
  - a page that words its date ambiguously is never guessed into a day;
- a record whose deadline has passed is never reminded about;
- the same reminder is never shown twice on the same day.

Nothing is sent anywhere: the notification is drawn by Windows, on this
device, and the reminder is switched off unless the student turns it on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

#: How many days before the deadline a reminder is shown.
REMINDER_DAYS: tuple[int, ...] = (30, 14, 7, 1)


@dataclass(frozen=True)
class Reminder:
    """One reminder, ready to be shown."""

    scholarship_id: int
    title: str
    deadline_date: str
    days_before: int
    source_url: str = ""
    message: str = ""


def _parse(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def days_until(deadline_date: str, today: date | None = None) -> int | None:
    """Days from today to the stored deadline, or None when there is no date."""
    parsed = _parse(deadline_date)
    if parsed is None:
        return None
    return (parsed - (today or date.today())).days


def is_due(deadline_date: str, today: date | None = None) -> bool:
    """True when the record falls on one of the reminder days."""
    remaining = days_until(deadline_date, today)
    if remaining is None:
        return False
    return remaining in REMINDER_DAYS


def reminder_message(title: str, deadline_date: str, days_before: int) -> str:
    """The sentence shown in the notification."""
    name = title or "A saved scholarship"
    if days_before == 1:
        return (
            f"{name} closes tomorrow ({deadline_date}). "
            "Open the page to check what it takes."
        )
    return (
        f"{name} closes in {days_before} days ({deadline_date}). "
        "Open the page to check what it takes."
    )


def due_reminders(
    records: Iterable[dict],
    today: date | None = None,
    saved_ids: Iterable[int] | None = None,
) -> list[Reminder]:
    """The reminders that are due today, for the saved records."""
    saved = None if saved_ids is None else {int(item) for item in saved_ids}
    reminders: list[Reminder] = []
    for record in records:
        record_id = int(record.get("id") or 0)
        if saved is not None and record_id not in saved:
            continue
        deadline = str(record.get("deadline_date") or "").strip()
        if not is_due(deadline, today):
            continue
        days = days_until(deadline, today)
        title = str(record.get("title") or "") or "A saved scholarship"
        reminders.append(
            Reminder(
                scholarship_id=record_id,
                title=title,
                deadline_date=deadline,
                days_before=int(days or 0),
                source_url=str(record.get("final_url") or record.get("requested_url") or ""),
                message=reminder_message(title, deadline, int(days or 0)),
            )
        )
    reminders.sort(key=lambda item: (item.deadline_date, item.title.casefold()))
    return reminders
