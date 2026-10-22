"""One name per page: the shell header names it, the body does not repeat it (G172).

The window's top bar carries the page name and a one-line description. Every
page used to draw its own big heading as well, so the same word appeared twice
("Settings" in the header and "Settings" again in the body). These tests hold
the line: one name, one description, and a body that starts with what the page
is for.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import scholarpath.ui.main_window as main_window
from scholarpath.config import AppConfig, PrivacyConfig
from scholarpath.gateway.stub import StubGateway
from scholarpath.ui.chat_controller import ChatController
from scholarpath.ui.main_window import MainWindow

PAGES = {
    "chat": "Chat Assistant",
    "profile": "My Profile",
    "documents": "Documents",
    "research": "Scholarship Pages",
    "eligibility": "Eligibility",
    "catalog": "Catalog",
    "discover": "Discover",
    "saved": "Saved Opportunities",
    "settings": "Settings",
}


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch) -> MainWindow:
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "titles.db")
    config = AppConfig(
        privacy=PrivacyConfig(voice_stt=False, voice_tts=False, web_search=False)
    )
    built = MainWindow(ChatController(StubGateway(), "stub"), config)
    yield built
    built.close()


def _labels(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel) if label.text()]


def test_the_page_name_is_shown_once(window: MainWindow) -> None:
    for name, title in PAGES.items():
        window.select_page(name)
        page = window._pages.currentWidget()

        assert window._page_title.text() == title
        assert title not in _labels(page), (
            f"the {name} page repeats its own name in the body"
        )


def test_the_subtitle_describes_the_page_without_repeating_its_name(
    window: MainWindow,
) -> None:
    for name, title in PAGES.items():
        window.select_page(name)
        subtitle = window.subtitle.text()

        assert subtitle, f"the {name} page has no description"
        assert not subtitle.startswith(title), (
            f"the {name} subtitle repeats the page name"
        )


def test_the_catalog_still_has_its_stored_records_heading(window: MainWindow) -> None:
    window.select_page("catalog")

    assert "Stored records" in _labels(window._pages.currentWidget())
