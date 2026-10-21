"""The window's page map must match the order the pages were added (G149).

The sidebar names are looked up in a literal index map, so a page inserted
without updating the map would silently open the wrong screen. These tests
build the real window and prove each name lands on its own page.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import scholarpath.ui.main_window as main_window
from scholarpath.config import AppConfig
from scholarpath.gateway.stub import StubGateway
from scholarpath.ui.chat_controller import ChatController
from scholarpath.ui.main_window import ActionTile, MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "nav.db")
    built = MainWindow(ChatController(StubGateway(), "stub"), AppConfig())
    yield built
    built.close()


def test_every_named_page_opens_the_page_it_names(window: MainWindow) -> None:
    expected = {
        "chat": window._pages.widget(0),
        "profile": window._profile_page,
        "documents": window._documents_page,
        "research": window._research_page,
        "eligibility": window._eligibility_page,
        "catalog": window._catalog_page,
        "discover": window._discover_page,
        "saved": window._saved_page,
        "settings": window._settings_page,
    }
    assert len(set(map(id, expected.values()))) == len(expected)

    for name, page in expected.items():
        window.select_page(name)
        assert window._pages.currentWidget() is page, name
        assert window._page_title.text()
        assert name in window._nav_buttons


def test_discover_reloads_when_it_is_opened(window: MainWindow) -> None:
    window._database.upsert_catalog_record(
        values={"title": "OPEN GRANT 2026", "deadline": "1 January 2030"},
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

    window.select_page("discover")

    assert "1 of 1 record(s) match" in window._discover_page._summary.text()


def test_explore_countries_quick_action_opens_discover(window: MainWindow) -> None:
    """G162: the tile is no longer a "Soon" placeholder."""
    target = None
    for tile in window.findChildren(ActionTile):
        titles = [
            label.text()
            for label in tile.findChildren(QLabel)
            if label.objectName() == "TileTitle"
        ]
        if "Explore Countries" in titles:
            target = tile
    assert target is not None

    target.click()

    assert window._pages.currentWidget() is window._discover_page


def test_no_quick_action_is_marked_soon(window: MainWindow) -> None:
    badges = [
        label.text()
        for label in window.findChildren(QLabel)
        if label.objectName() == "TileBadge"
    ]
    assert "Soon" not in badges
