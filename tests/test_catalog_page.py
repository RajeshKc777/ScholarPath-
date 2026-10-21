"""The Catalog page: the registry list, the progress panel and stored records.

The Qt widgets are built for real, but the crawl itself is never started here -
these tests check what the page shows, not that HTTP works.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scholarpath.ui.catalog_page as page_module
from scholarpath.catalog import CatalogEvent, CatalogStats
from scholarpath.registry import RegistryError, Source
from scholarpath.storage import Database
from scholarpath.ui.catalog_page import CatalogPage, RecordCard, SourceRow


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "page.db")
    yield database
    database.close()


def make_source(name: str = "Example Portal", enabled: bool = True) -> Source:
    return Source(
        name=name,
        base_url="https://example.gov/scholarships",
        country="Netherlands",
        trust_level="official",
        allowed_path_prefixes=("/scholarships",),
        crawl_depth=1,
        enabled=enabled,
    )


def make_page(db: Database, monkeypatch, sources: list[Source]) -> CatalogPage:
    monkeypatch.setattr(page_module, "load_registry", lambda: sources)
    monkeypatch.setattr(
        page_module, "user_registry_path", lambda: Path("C:/nowhere/sources_registry.toml")
    )
    return CatalogPage(db, object())


def test_the_page_lists_every_portal_in_the_registry(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source(), make_source("Second Portal")])
    assert isinstance(page._rows[0], SourceRow)
    assert [row.source.name for row in page._rows] == ["Example Portal", "Second Portal"]
    assert page._run_button.isEnabled()
    assert "2 official portal(s)" in page._registry_note.text()


def test_a_broken_registry_disables_the_run(db: Database, monkeypatch) -> None:
    def broken() -> list[Source]:
        raise RegistryError("line 4: the entry has no base_url")

    monkeypatch.setattr(page_module, "load_registry", broken)
    page = CatalogPage(db, object())
    assert page._rows == []
    assert not page._run_button.isEnabled()
    assert "line 4" in page._registry_note.text()


def test_only_switched_on_portals_are_run(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source("On"), make_source("Off", enabled=False)])
    selected = page._selected_sources()
    assert [source.name for source in selected] == ["On"]
    assert selected[0].enabled is True


def test_a_run_with_nothing_selected_says_so(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source(enabled=False)])
    page._start()
    assert page._job is None
    assert "pick at least one" in page._status.text()


def test_errors_are_counted_in_the_error_box(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source()])
    page._on_progress_event(
        CatalogEvent(kind="error", message="https://example.gov/x - HTTP 500", errors=1)
    )
    assert page._errors.isVisibleTo(page) is True
    assert "HTTP 500" in page._errors.toPlainText()


def test_the_finish_line_reports_the_honest_totals(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source()])
    page._run_button.setEnabled(False)
    page._cancel_button.setEnabled(True)
    page._on_finished(CatalogStats(sources=1, pages_read=3, records_created=1, errors=2))
    assert page._job is None
    assert page._run_button.isEnabled()
    assert not page._cancel_button.isEnabled()
    assert "3 page(s) read" in page._status.text()
    assert "2 error(s)" in page._status.text()


def test_a_failed_run_is_shown_not_swallowed(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source()])
    page._on_failed("the model is rate-limited")
    assert page._job is None
    assert page._run_button.isEnabled()
    assert "rate-limited" in page._status.text()


def test_stored_records_are_listed_with_their_pages(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source()])
    assert page._records.count() == 2  # the placeholder and the stretch

    db.upsert_catalog_record(
        values={"title": "OPEN GRANT 2026", "deadline": "5 November 2026"},
        unknown=[],
        warnings=[],
        source_url="https://example.gov/open-grant",
        final_url="https://example.gov/open-grant",
        retrieved_at="2026-10-21T10:00:00",
        page_sha256="hash",
        page_title="OPEN GRANT 2026",
        provider="Example Portal",
        provider_domain="example.gov",
    )
    page.reload()
    cards = [
        page._records.itemAt(index).widget()
        for index in range(page._records.count())
        if isinstance(page._records.itemAt(index).widget(), RecordCard)
    ]
    assert len(cards) == 1


def test_shutdown_cancels_a_running_job(db: Database, monkeypatch) -> None:
    page = make_page(db, monkeypatch, [make_source()])
    page.shutdown()
    assert page._cancel.is_set() is True
