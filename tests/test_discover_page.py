"""The Discover page: search, filters, saving, and the profile hand-off (G149, G150).

Records are seeded through the same storage call the catalog run uses, so the
tests exercise the real shapes. The eligibility dialog is replaced by a fake in
the hand-off tests - the real card is already covered by the Eligibility page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

import scholarpath.ui.discover_page as page_module
from scholarpath.eligibility import SATISFIED, UNKNOWN, evaluate
from scholarpath.storage import Database
from scholarpath.ui.discover_page import DiscoverPage, RecordCard


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "discover.db")
    yield database
    database.close()


def seed(
    db: Database,
    *,
    title: str = "OPEN GRANT 2026",
    provider: str = "Example Portal",
    domain: str = "example.gov",
    deadline: str = "1 January 2030",
    source_url: str = "https://example.gov/open-grant",
    values: dict | None = None,
) -> int:
    record_id, _action = db.upsert_catalog_record(
        values={
            "title": title,
            "host_country": "Netherlands",
            "degree_levels": "master's degrees",
            "disciplines": "economics, public policy",
            "funding_coverage": "fully funded tuition",
            "deadline": deadline,
            "language_requirement": "IELTS 6.5",
            "application_url": source_url + "/apply",
            **(values or {}),
        },
        unknown=[],
        warnings=[],
        source_url=source_url,
        final_url=source_url,
        retrieved_at="2026-10-21T10:00:00",
        page_sha256="hash",
        page_title=title,
        provider=provider,
        provider_domain=domain,
    )
    return record_id


def cards(page: DiscoverPage) -> list[RecordCard]:
    found = []
    for index in range(page._list.count()):
        widget = page._list.itemAt(index).widget()
        if isinstance(widget, RecordCard):
            found.append(widget)
    return found


def labels_of(card: RecordCard) -> str:
    return " | ".join(
        label.text() for label in card.findChildren(QLabel) if label.text()
    )


def test_the_page_lists_what_the_catalog_holds(db: Database) -> None:
    seed(db)
    seed(db, title="SECOND GRANT", source_url="https://example.gov/second")
    page = DiscoverPage(db)

    assert len(cards(page)) == 2
    assert "2 of 2 record(s) match" in page._summary.text()


def test_the_search_box_narrows_the_list(db: Database) -> None:
    seed(db)
    seed(
        db,
        title="JAPAN GRANT",
        provider="Japan Portal",
        domain="studyinjapan.go.jp",
        deadline="1 March 2027",
        source_url="https://studyinjapan.go.jp/grant",
        values={"host_country": "Japan"},
    )
    page = DiscoverPage(db)

    page._search.setText("netherlands")

    assert len(cards(page)) == 1
    assert cards(page)[0].record["title"] == "OPEN GRANT 2026"
    assert "1 of 2 record(s) match" in page._summary.text()


def test_the_level_filter_uses_the_pages_wording(db: Database) -> None:
    seed(db)  # master's degrees
    seed(
        db,
        title="DOCTORAL GRANT",
        source_url="https://example.gov/doctoral",
        values={"degree_levels": "doctoral programme"},
    )
    page = DiscoverPage(db)

    page._level.setCurrentIndex(page._level.findData("phd"))

    assert [card.record["title"] for card in cards(page)] == ["DOCTORAL GRANT"]


def test_the_deadline_filter_excludes_closed_and_undated_records(db: Database) -> None:
    seed(db)
    seed(
        db,
        title="CLOSED GRANT",
        source_url="https://example.gov/closed",
        deadline="1 January 2026",
    )
    seed(
        db,
        title="UNDATED GRANT",
        source_url="https://example.gov/undated",
        deadline="",
    )
    page = DiscoverPage(db)

    page._deadline.setCurrentIndex(page._deadline.findData("open"))

    titles = [card.record["title"] for card in cards(page)]
    assert titles == ["OPEN GRANT 2026"]


def test_clearing_the_filters_brings_everything_back(db: Database) -> None:
    seed(db)
    seed(db, title="JAPAN GRANT", provider="Japan Portal", source_url="https://example.gov/j")
    page = DiscoverPage(db)
    page._search.setText("nothing matches this")
    assert cards(page) == []

    page._clear_filters()

    assert len(cards(page)) == 2
    assert page._search.text() == ""
    assert page._level.currentData() == "any"
    assert page._deadline.currentData() == "any"


def test_an_empty_catalog_says_where_to_start(db: Database) -> None:
    page = DiscoverPage(db)
    assert cards(page) == []
    assert page._summary.text() == "The catalog is empty."
    assert "Run the Catalog page first" in labels_of_placeholder(page)


def labels_of_placeholder(page: DiscoverPage) -> str:
    widget = page._list.itemAt(0).widget()
    return widget.text() if isinstance(widget, QLabel) else ""


def test_an_empty_result_is_not_an_empty_catalog(db: Database) -> None:
    seed(db)
    page = DiscoverPage(db)
    page._search.setText("no such scholarship")
    assert "No record matches these filters" in page._summary.text()
    assert "No record matches these filters" in labels_of_placeholder(page)


def test_the_card_keeps_the_page_wording_and_the_parsed_state(db: Database) -> None:
    seed(db)
    page = DiscoverPage(db)
    text = labels_of(cards(page)[0])
    assert 'The page says: "1 January 2030"' in text
    assert "OPEN" in text
    assert "1 page(s) behind this record" in text


def test_saving_from_discover_writes_the_saved_list(db: Database) -> None:
    record_id = seed(db)
    page = DiscoverPage(db)
    assert db.is_saved(record_id) is False

    page._toggle_save(record_id, True)

    assert db.is_saved(record_id) is True
    assert any(
        "Saved" in button.text() for button in cards(page)[0].findChildren(QPushButton)
    )

    page._toggle_save(record_id, False)

    assert db.is_saved(record_id) is False


def test_the_provider_filter_lists_only_stored_portals(db: Database) -> None:
    seed(db)
    seed(db, title="JAPAN GRANT", provider="Japan Portal", domain="example.jp",
         source_url="https://example.jp/grant")
    page = DiscoverPage(db)

    options = [page._provider.itemText(index) for index in range(page._provider.count())]

    assert options == ["Any portal", "Example Portal", "Japan Portal"]


def test_browsing_never_changes_a_record(db: Database) -> None:
    record_id = seed(db)
    before = next(db.catalog_records())
    page = DiscoverPage(db)
    page._search.setText("grant")
    page._level.setCurrentIndex(page._level.findData("master"))
    page.reload()

    after = next(db.catalog_records())
    assert after["id"] == record_id
    assert after["data"] == before["data"]
    assert after["deadline_date"] == before["deadline_date"]


# -- the hand-off to the deterministic engine ---------------------------------


class _FakeDialog:
    captured: dict = {}

    def __init__(self, report, **kwargs) -> None:
        _FakeDialog.captured = {"report": report, **kwargs}
        self.report = report

    def exec(self) -> int:  # stand in for the modal dialog
        return 0


def _page_with_fake_dialog(db: Database, monkeypatch) -> DiscoverPage:
    _FakeDialog.captured = {}
    monkeypatch.setattr(page_module, "EligibilityDialog", _FakeDialog)
    return DiscoverPage(db)


def test_the_hand_off_runs_the_real_engine_on_verified_values(db: Database, monkeypatch) -> None:
    record_id = seed(
        db,
        values={
            "eligible_nationalities": "Nepal\nIndia",
            "degree_levels": "master's degrees",
            "language_requirement": "IELTS 6.5",
        },
    )
    db.save_profile(
        {
            "nationality": "Nepal",
            "degree_level": "master",
            "ielts": "7.0",
        }
    )
    page = _page_with_fake_dialog(db, monkeypatch)
    record = next(db.catalog_records())

    page._check(record)

    report = _FakeDialog.captured["report"]
    # The same engine, the same states: nothing is invented by the hand-off.
    expected = evaluate(
        {
            "nationality": "Nepal",
            "degree_level": "master",
            "ielts": "7.0",
            "gpa": "",
            "gpa_scale": "",
            "toefl": "",
        },
        record,
    )
    assert [r.state for r in report.requirements] == [
        r.state for r in expected.requirements
    ]
    assert report.scholarship_id == record_id
    assert report.state_of("nationality") == SATISFIED
    assert report.state_of("language") == SATISFIED
    assert _FakeDialog.captured["profile_empty"] is False
    assert "eligible" not in report.verdict().casefold()


def test_the_hand_off_says_so_when_the_profile_is_empty(db: Database, monkeypatch) -> None:
    seed(db)
    page = _page_with_fake_dialog(db, monkeypatch)

    page._check(next(db.catalog_records()))

    report = _FakeDialog.captured["report"]
    assert _FakeDialog.captured["profile_empty"] is True
    assert report.state_of("nationality") == UNKNOWN
    assert "need checking" in report.verdict()


def test_the_hand_off_does_not_mark_anything_eligible(db: Database, monkeypatch) -> None:
    seed(db)
    db.save_profile({"nationality": "Nepal", "degree_level": "master"})
    page = _page_with_fake_dialog(db, monkeypatch)
    page._check(next(db.catalog_records()))

    verdict = _FakeDialog.captured["report"].verdict().casefold()
    assert "you are eligible" not in verdict
    assert "confirmed" not in verdict or "confirm on the official page" in verdict
