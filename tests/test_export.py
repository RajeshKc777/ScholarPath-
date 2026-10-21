"""Exporting the saved list: what the CSV and the calendar file contain (G157)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scholarpath.export import CSV_COLUMNS, csv_text, ics_event_count, ics_text
from scholarpath.storage import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "export.db")
    yield database
    database.close()


def seed(
    db: Database,
    *,
    title: str = "OPEN GRANT 2026",
    deadline_text: str = "5 November 2026",
    deadline_date: str | None = "2026-11-05",
    url: str = "https://example.gov/open-grant",
) -> int:
    values = {
        "title": title,
        "host_country": "Netherlands",
        "degree_levels": "master's degrees",
        "funding_coverage": "fully funded tuition",
        "deadline": deadline_text,
    }
    record_id, _action = db.upsert_catalog_record(
        values=values,
        unknown=[],
        warnings=[],
        source_url=url,
        final_url=url,
        retrieved_at="2026-10-01T09:00:00",
        page_sha256="hash",
        page_title=title,
        provider="Example Portal",
        provider_domain="example.gov",
    )
    with db._lock:
        db._connection.execute(
            "UPDATE scholarship SET deadline_date = ? WHERE id = ?",
            (deadline_date, record_id),
        )
    return record_id


def rows_of(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


# -- CSV ----------------------------------------------------------------------


def test_the_csv_has_one_row_per_saved_record(db: Database) -> None:
    seed(db)
    seed(db, title="SECOND GRANT", url="https://example.gov/second")

    rows = rows_of(csv_text(list(db.catalog_records())))

    assert len(rows) == 2
    assert list(rows[0].keys()) == list(CSV_COLUMNS)


def test_the_csv_keeps_the_deadline_text_exactly_as_the_page_wrote_it(db: Database) -> None:
    seed(db, deadline_text="5 November 2026, 5pm CET")

    rows = rows_of(csv_text(list(db.catalog_records())))

    assert rows[0]["Deadline (as written on the page)"] == "5 November 2026, 5pm CET"


def test_the_csv_carries_the_source_url_and_the_last_verified_day(db: Database) -> None:
    seed(db)

    rows = rows_of(csv_text(list(db.catalog_records())))

    assert rows[0]["Source URL"] == "https://example.gov/open-grant"
    assert rows[0]["Last verified"] == "2026-10-01"
    assert rows[0]["Deadline date"] == "2026-11-05"


def test_a_field_the_page_never_stated_is_empty_in_the_csv(db: Database) -> None:
    seed(db)

    rows = rows_of(csv_text(list(db.catalog_records())))

    assert rows[0]["Amount"] == ""


# -- the calendar file --------------------------------------------------------


def test_the_calendar_file_holds_one_event_per_record_with_a_date(db: Database) -> None:
    seed(db)

    text = ics_text(list(db.catalog_records()), now=datetime(2026, 10, 21, tzinfo=timezone.utc))

    assert text.startswith("BEGIN:VCALENDAR")
    assert "VERSION:2.0" in text
    assert text.count("BEGIN:VEVENT") == 1
    assert "DTSTART;VALUE=DATE:20261105" in text
    assert "SUMMARY:OPEN GRANT 2026" in text
    assert text.rstrip().endswith("END:VCALENDAR")
    assert "\r\n" in text


def test_a_record_without_a_readable_date_becomes_no_event(db: Database) -> None:
    seed(db, deadline_date=None)

    records = list(db.catalog_records())
    text = ics_text(records)

    assert "BEGIN:VEVENT" not in text
    assert ics_event_count(records) == 0


def test_the_event_describes_the_deadline_and_the_source(db: Database) -> None:
    seed(db)

    text = ics_text(list(db.catalog_records()))

    assert "Deadline as written on the page: 5 November 2026" in text
    assert "https://example.gov/open-grant" in text
    assert "Last verified: 2026-10-01" in text


def test_the_special_characters_are_escaped(db: Database) -> None:
    seed(db, title="GRANT, PART A; THE SECOND")

    text = ics_text(list(db.catalog_records()))

    assert "SUMMARY:GRANT\\, PART A\\; THE SECOND" in text


def test_a_long_line_is_folded(db: Database) -> None:
    seed(db, title="A" * 200)

    text = ics_text(list(db.catalog_records()))

    lines = text.split("\r\n")
    assert any(line.startswith(" ") for line in lines)
    assert all(len(line.encode("utf-8")) <= 75 for line in lines if line)
