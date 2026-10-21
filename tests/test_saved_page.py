"""The Saved page: freshness states, the difference, warning signs, export (G152-G158)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from scholarpath.freshness import (
    STATE_EXPIRED,
    STATUS_CHANGED,
    STATUS_FAILED,
    FieldDiff,
    RefreshResult,
)
from scholarpath.storage import Database
from scholarpath.ui.saved_page import SavedPage


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "saved.db")
    yield database
    database.close()


def seed(
    db: Database,
    *,
    title: str = "OPEN GRANT 2026",
    url: str = "https://example.gov/open-grant",
    deadline_text: str = "5 November 2026",
    deadline_date: str | None = "2026-11-05",
    page_text: str = "Deadline: 5 November 2026",
) -> int:
    record_id, _action = db.upsert_catalog_record(
        values={
            "title": title,
            "host_country": "Netherlands",
            "degree_levels": "master's degrees",
            "deadline": deadline_text,
        },
        unknown=[],
        warnings=[],
        source_url=url,
        final_url=url,
        retrieved_at="2026-10-01T09:00:00",
        page_sha256="hash",
        page_title=title,
        provider="Example Portal",
        provider_domain="example.gov",
        page_text=page_text,
    )
    with db._lock:
        db._connection.execute(
            "UPDATE scholarship SET deadline_date = ? WHERE id = ?",
            (deadline_date, record_id),
        )
    return record_id


def card_texts(page: SavedPage) -> str:
    return " | ".join(
        label.text() for label in page.findChildren(QLabel) if label.text()
    )


def buttons(page: SavedPage) -> list[str]:
    return [button.text() for button in page.findChildren(QPushButton)]


# -- the freshness states -----------------------------------------------------


def test_a_failed_check_is_shown_on_the_card(db: Database) -> None:
    record_id = seed(db)
    db.save_opportunity(record_id)
    db.mark_checked(
        record_id,
        checked_at="2026-10-21T09:00:00",
        status=STATUS_FAILED,
        detail="could not re-check, last verified 2026-10-01",
    )

    page = SavedPage(db)

    assert "could not re-check, last verified 2026-10-01" in card_texts(page)


def test_a_record_whose_deadline_passed_is_marked_expired(db: Database) -> None:
    record_id = seed(db, deadline_date="2026-01-01")
    db.save_opportunity(record_id)

    page = SavedPage(db)

    assert "EXPIRED" in card_texts(page)


def test_a_record_without_a_readable_date_is_not_marked_expired(db: Database) -> None:
    record_id = seed(db, deadline_date=None, deadline_text="soon")
    db.save_opportunity(record_id)

    page = SavedPage(db)

    assert "EXPIRED" not in card_texts(page)


def test_the_change_is_shown_with_the_old_and_the_new_value(db: Database) -> None:
    record_id = seed(db)
    db.save_opportunity(record_id)
    page = SavedPage(db)
    page._refresh_results[record_id] = RefreshResult(
        scholarship_id=record_id,
        url="https://example.gov/open-grant",
        status=STATUS_CHANGED,
        detail="1 field(s) changed.",
        diffs=[
            FieldDiff(
                field="deadline",
                old="5 November 2026",
                new="30 November 2026",
                evidence="Deadline: 30 November 2026",
            )
        ],
    )
    page.reload()

    text = card_texts(page)
    assert "the page changed" in text
    assert "was \"5 November 2026\"" in text
    assert "now \"30 November 2026\"" in text
    assert "Deadline: 30 November 2026" in text
    assert "Show what changed" in buttons(page)


def test_the_change_is_still_shown_after_a_restart(db: Database) -> None:
    """The difference is kept with the record, not only in this run's memory."""
    record_id = seed(db)
    db.save_opportunity(record_id)
    db.apply_refresh(
        record_id,
        values={"deadline": "30 November 2026"},
        page_sha256="new-hash",
        retrieved_at="2026-10-21T09:00:00",
        checked_at="2026-10-21T09:00:00",
        status=STATUS_CHANGED,
        diffs=[
            {
                "field": "deadline",
                "old": "5 November 2026",
                "new": "30 November 2026",
                "evidence": "Deadline: 30 November 2026",
            }
        ],
    )

    page = SavedPage(db)  # a fresh page: nothing in memory

    text = card_texts(page)
    assert "the page changed" in text
    assert "Show what changed" in buttons(page)
    assert "Deadline: 30 November 2026" in text


# -- the warning signs --------------------------------------------------------

def test_a_lookalike_domain_shows_a_warning_sign(db: Database) -> None:
    record_id = seed(db, url="https://harvard.edu.fake.com/x")
    db.save_opportunity(record_id)

    page = SavedPage(db)

    text = card_texts(page)
    assert "warning sign" in text.casefold()
    assert "Why this record?" in buttons(page)


def test_a_trusted_domain_shows_no_warning_sign(db: Database) -> None:
    record_id = seed(db, url="https://www.chevening.org/scholarships/")
    db.save_opportunity(record_id)

    page = SavedPage(db, trusted_domains=["chevening.org"])

    assert "warning sign" not in card_texts(page).casefold()


# -- the export ---------------------------------------------------------------


def test_the_export_buttons_are_offered(db: Database) -> None:
    seed(db)

    page = SavedPage(db)

    assert "Export CSV" in buttons(page)
    assert "Export calendar" in buttons(page)


def test_the_csv_is_written_from_the_saved_list(db: Database, tmp_path: Path) -> None:
    record_id = seed(db)
    db.save_opportunity(record_id)
    page = SavedPage(db)

    target = tmp_path / "saved.csv"
    page._write_file(str(target), "a,b\r\n")

    assert target.read_bytes() == b"a,b\r\n"


def test_a_nothing_saved_export_says_so(db: Database) -> None:
    page = SavedPage(db)

    page._export_csv()

    assert "nothing saved" in page._recheck_status.text().casefold()


# -- the list holds up with more records (G163) -------------------------------


def test_the_card_list_scrolls_with_more_records(db: Database) -> None:
    for index in range(5):
        seed(
            db,
            title=f"GRANT {index}",
            url=f"https://example.gov/grant-{index}",
        )

    page = SavedPage(db)

    assert isinstance(page._list, QScrollArea)
    assert page._list.widgetResizable()
    assert page._list.widget() is page._body.parentWidget()


def test_the_saved_date_is_a_date_not_a_timestamp(db: Database) -> None:
    record_id = seed(db)
    db.save_opportunity(record_id)

    page = SavedPage(db)

    text = card_texts(page)
    assert "saved 2026-10-01" in text
    assert "2026-10-01T09:00:00" not in text

