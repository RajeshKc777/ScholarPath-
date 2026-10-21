"""Deadline reminders: the schedule, the switch, and no repeats (G156)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scholarpath.reminders import (
    REMINDER_DAYS,
    days_until,
    due_reminders,
    is_due,
    reminder_message,
)
from scholarpath.storage import Database
from scholarpath.ui.reminders import ReminderService


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "reminders.db")
    yield database
    database.close()


def seed(db: Database, *, deadline: str | None, title: str = "OPEN GRANT 2026") -> int:
    values = {"title": title, "deadline": "5 November 2026"}
    record_id, _action = db.upsert_catalog_record(
        values=values,
        unknown=[],
        warnings=[],
        source_url="https://example.gov/open-grant",
        final_url="https://example.gov/open-grant",
        retrieved_at="2026-10-01T09:00:00",
        page_sha256="hash",
        page_title=title,
        provider="Example Portal",
        provider_domain="example.gov",
    )
    # The stored date is what the reminder reads; the page wording above is
    # only how the record was created.
    with db._lock:
        db._connection.execute(
            "UPDATE scholarship SET deadline_date = ? WHERE id = ?",
            (deadline, record_id),
        )
    return record_id


def test_the_schedule_is_30_14_7_and_1_days() -> None:
    assert REMINDER_DAYS == (30, 14, 7, 1)


def test_a_deadline_seven_days_away_is_due() -> None:
    assert is_due("2026-10-28", date(2026, 10, 21)) is True
    assert days_until("2026-10-28", date(2026, 10, 21)) == 7


def test_a_deadline_six_days_away_is_not_due() -> None:
    assert is_due("2026-10-27", date(2026, 10, 21)) is False


def test_a_record_without_a_readable_date_is_never_due() -> None:
    assert is_due("", date(2026, 10, 21)) is False
    assert is_due("not a date", date(2026, 10, 21)) is False


def test_a_deadline_that_has_passed_is_never_due() -> None:
    assert is_due("2026-10-01", date(2026, 10, 21)) is False


def test_only_a_saved_record_is_reminded_about(db: Database) -> None:
    record_id = seed(db, deadline="2026-10-28")
    records = list(db.catalog_records())

    assert due_reminders(records, date(2026, 10, 21), saved_ids=[]) == []

    db.save_opportunity(record_id)
    records = list(db.catalog_records())
    reminders = due_reminders(records, date(2026, 10, 21), saved_ids=[record_id])

    assert len(reminders) == 1
    assert reminders[0].days_before == 7
    assert reminders[0].scholarship_id == record_id
    assert "closes in 7 days" in reminders[0].message


def test_the_message_names_the_record_and_the_day(db: Database) -> None:
    record_id = seed(db, deadline="2026-10-22")
    db.save_opportunity(record_id)
    reminders = due_reminders(
        list(db.catalog_records()), date(2026, 10, 21), saved_ids=[record_id]
    )
    assert "tomorrow" in reminders[0].message
    assert "OPEN GRANT 2026" in reminders[0].message


def test_the_message_for_the_far_days_is_plain() -> None:
    text = reminder_message("OPEN GRANT 2026", "2026-11-20", 30)
    assert "closes in 30 days" in text


# -- the service (the switch) -------------------------------------------------


def test_nothing_is_shown_while_the_switch_is_off(db: Database) -> None:
    record_id = seed(db, deadline="2026-10-28")
    db.save_opportunity(record_id)
    shown: list[tuple[str, str]] = []

    service = ReminderService(
        db, enabled=False, notify=lambda title, text: shown.append((title, text)) or True
    )

    assert service.show_due(date(2026, 10, 21)) == []
    assert shown == []


def test_a_due_reminder_is_shown_once(db: Database) -> None:
    record_id = seed(db, deadline="2026-10-28")
    db.save_opportunity(record_id)
    shown: list[tuple[str, str]] = []

    service = ReminderService(
        db, enabled=True, notify=lambda title, text: shown.append((title, text)) or True
    )

    first = service.show_due(date(2026, 10, 21))
    second = service.show_due(date(2026, 10, 21))

    assert len(first) == 1
    assert second == []
    assert len(shown) == 1


def test_the_reminder_is_not_shown_again_after_its_day_has_passed(db: Database) -> None:
    record_id = seed(db, deadline="2026-10-28")
    db.save_opportunity(record_id)
    shown: list[tuple[str, str]] = []

    service = ReminderService(
        db, enabled=True, notify=lambda title, text: shown.append((title, text)) or True
    )

    service.show_due(date(2026, 10, 21))
    service.show_due(date(2026, 10, 22))

    # 28 October is six days away on the 22nd: the reminder window has passed.
    assert len(shown) == 1
