"""UI truthfulness: privacy gates, config-driven copy, elision and the avatar.

These build the real MainWindow. They are deliberately about what a student
sees, not about the gateway internals: a control that privacy keeps off must be
disabled, say where to turn it on, and take a click to that explanation.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea

import scholarpath.ui.main_window as main_window
from scholarpath.config import AppConfig, PrivacyConfig, load_config
from scholarpath.gateway.stub import StubGateway
from scholarpath.ui.chat_controller import ChatController
from scholarpath.ui.main_window import GLYPH_PERSON, ActionTile, MainWindow


class LiveStub(StubGateway):
    """A stub that reports itself as a live connection (for copy tests)."""

    name = "fake"


def _window(tmp_path, monkeypatch, privacy: PrivacyConfig | None = None, live: bool = False) -> MainWindow:
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "ui.db")
    config = AppConfig(
        privacy=privacy
        or PrivacyConfig(voice_stt=False, voice_tts=False, web_search=False)
    )
    gateway = LiveStub() if live else StubGateway()
    controller = ChatController(
        gateway, "stub", search_enabled=config.privacy.web_search
    )
    return MainWindow(controller, config)


@pytest.fixture
def window(tmp_path, monkeypatch):
    built = _window(tmp_path, monkeypatch)
    yield built
    built.close()


def _tile(window: MainWindow, title: str) -> ActionTile:
    for tile in window.findChildren(ActionTile):
        labels = [
            label.text()
            for label in tile.findChildren(main_window.QLabel)
            if label.objectName() == "TileTitle"
        ]
        if title in labels:
            return tile
    raise AssertionError(f"no quick-action tile titled {title!r}")


def test_voice_controls_are_disabled_and_point_at_privacy(window: MainWindow) -> None:
    assert not window.mic_button.isEnabled()
    assert not window.voice_mode_button.isEnabled()
    reason = "Off. Turn on in Settings > Privacy"
    assert window._mic_gate.toolTip() == reason
    assert window._voice_gate.toolTip() == reason
    assert window._capability_tags["voice"].text() == "Off"


def test_turning_privacy_on_enables_the_controls(window: MainWindow) -> None:
    window._config.privacy.voice_stt = True
    window._config.privacy.voice_tts = True

    window._refresh_status()

    assert window.mic_button.isEnabled()
    assert window.voice_mode_button.isEnabled()
    assert window._mic_gate.toolTip() == ""
    assert window._voice_gate.toolTip() == ""
    assert window._capability_tags["voice"].text() == "On"


def test_a_settings_toggle_updates_the_window_and_saves(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "toggle.db")
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "[privacy]\nvoice_stt = false\nvoice_tts = false\nweb_search = false\n",
        encoding="utf-8",
    )
    config = AppConfig(
        privacy=PrivacyConfig(voice_stt=False, voice_tts=False, web_search=False)
    )
    controller = ChatController(StubGateway(), "stub", search_enabled=False)
    window = MainWindow(controller, config, config_file=config_file)
    try:
        rows = window._settings_page._privacy_rows
        rows["voice_stt"].toggle.click()

        assert config.privacy.voice_stt is True
        assert load_config(config_file).privacy.voice_stt is True
        assert window.mic_button.isEnabled()

        rows["web_search"].toggle.click()

        assert config.privacy.web_search is True
        assert controller.search_enabled is True
        assert window._capability_tags["web"].text() == "On"
    finally:
        window._database.close()
        window.close()


def test_a_gated_control_opens_the_privacy_section(window: MainWindow, monkeypatch) -> None:
    window.show()
    called: list[bool] = []
    monkeypatch.setattr(
        window._settings_page, "focus_privacy", lambda: called.append(True)
    )

    QTest.mouseClick(window._mic_gate._shield, Qt.LeftButton)

    assert window._page_name == "settings"
    assert called == [True]


def test_status_elides_only_between_words_and_keeps_the_full_tooltip(
    window: MainWindow,
) -> None:
    full = "Live voice is off. Turn it on in Settings > Privacy. " * 4
    window._notice = full
    window.status.setFixedWidth(180)

    window._refresh_status()

    shown = window.status.text()
    assert shown.endswith("\u2026")
    assert window.status.toolTip() == full
    visible_words = shown[:-1].strip().split()
    assert visible_words
    assert visible_words[-1] in full.split()


def test_a_short_status_is_not_elided(window: MainWindow) -> None:
    window._notice = "Short notice."
    window.status.setFixedWidth(800)

    window._refresh_status()

    assert window.status.text() == "Short notice."


def test_chat_copy_and_what_works_follow_the_privacy_config(
    tmp_path, monkeypatch
) -> None:
    config = AppConfig()
    config.privacy = PrivacyConfig(web_search=False, voice_stt=False, voice_tts=False)
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "copy.db")
    window = MainWindow(ChatController(LiveStub(), "stub"), config)
    try:
        window._refresh_status()
        assert "web search off (enable in settings)" in window.subtitle.text().casefold()
        assert "web search off (enable in settings)" in window.hint.text().casefold()
        assert "web search off (enable in settings)" in window.status.full_text().casefold()
        assert window._capability_tags["web"].text() == "Off"
        assert window._capability_tags["voice"].text() == "Off"

        config.privacy.web_search = True
        config.privacy.voice_stt = True
        config.privacy.voice_tts = True
        window._refresh_status()

        assert "web search on" in window.subtitle.text().casefold()
        assert "web search on" in window.hint.text().casefold()
        assert "no web search yet" in window.status.full_text().casefold()
        assert window._capability_tags["web"].text() == "On"
        assert window._capability_tags["voice"].text() == "On"
    finally:
        window.close()


def test_avatar_uses_the_first_letter_or_a_person_icon(window: MainWindow) -> None:
    assert window._avatar.text() == GLYPH_PERSON

    window._database.save_profile({"student_name": "Aarav Sharma"})
    window._refresh_profile_panel()
    assert window._avatar.text() == "A"

    window._database.save_profile({"student_name": "   "})
    window._refresh_profile_panel()
    assert window._avatar.text() == GLYPH_PERSON


def test_profile_page_is_inside_a_scroll_area(window: MainWindow) -> None:
    assert isinstance(window._profile_scroll, QScrollArea)
    assert window._profile_scroll.widget() is window._profile_page

    window.select_page("profile")
    assert window._pages.currentWidget() is window._profile_scroll


def test_find_scholarships_opens_discover_and_focuses_the_search(
    window: MainWindow, monkeypatch
) -> None:
    focused: list[bool] = []
    monkeypatch.setattr(
        window._discover_page, "focus_search", lambda: focused.append(True)
    )

    _tile(window, "Find Scholarships").click()

    assert window._pages.currentWidget() is window._discover_page
    assert focused == [True]


def test_the_config_path_is_a_tooltip_not_a_competing_label(window: MainWindow) -> None:
    assert window._config_path_label.text() == "Config"
    assert "config.toml" in window._config_path_label.toolTip()


def test_right_panel_needs_no_scroll_at_the_default_size(window: MainWindow) -> None:
    window.resize(1120, 720)
    window.show()
    QApplication.processEvents()

    assert not window._right_scroll.verticalScrollBar().isVisible()
