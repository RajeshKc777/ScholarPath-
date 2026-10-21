"""The privacy switches, the new sections, and what the Settings page says (G159).

Every switch is off by default, each feature is gated on its own switch, and
the Settings page names the third party and the data for each one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from scholarpath.config import (
    AppConfig,
    ConfigError,
    FreshnessConfig,
    RemindersConfig,
    load_config,
)
from scholarpath.ui.settings_page import SettingsPage


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# -- the switches (G159) ------------------------------------------------------


def test_every_privacy_switch_is_off_by_default() -> None:
    privacy = AppConfig().privacy
    assert privacy.voice_stt is False
    assert privacy.voice_tts is False
    assert privacy.web_search is False


def test_the_reminder_switch_is_off_by_default() -> None:
    assert AppConfig().reminders.enabled is False


def test_the_reminders_are_off_until_the_student_turns_them_on(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[reminders]\nenabled = true\n", encoding="utf-8")

    config = load_config(path)

    assert config.reminders.enabled is True


def test_the_freshness_section_parses(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "[freshness]\nauto = false\ninterval_hours = 6\nmax_per_run = 5\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.freshness.auto is False
    assert config.freshness.interval_hours == 6
    assert config.freshness.max_per_run == 5


def test_an_impossible_freshness_value_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[freshness]\ninterval_hours = 0\n", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert "interval_hours" in str(excinfo.value)


def test_an_unknown_freshness_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[freshness]\nbogus = true\n", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert "bogus" in str(excinfo.value)


def test_the_shipped_template_loads() -> None:
    config = AppConfig()
    assert isinstance(config.freshness, FreshnessConfig)
    assert isinstance(config.reminders, RemindersConfig)


# -- the Settings page --------------------------------------------------------


def _texts(page: SettingsPage) -> str:
    return " ".join(
        label.text() for label in page.findChildren(QLabel) if label.text()
    ).casefold()


def test_the_settings_page_names_the_third_party_for_every_switch(app) -> None:
    page = SettingsPage(AppConfig(), gateway_name=lambda: "stub", stats=lambda: {})

    text = _texts(page)

    assert "google's speech service" in text
    assert "microsoft's speech service" in text
    assert "duckduckgo" in text
    assert "voice_stt" in text
    assert "voice_tts" in text
    assert "web_search" in text


def test_the_settings_page_says_the_reminder_stays_on_this_device(app) -> None:
    page = SettingsPage(AppConfig(), gateway_name=lambda: "stub", stats=lambda: {})

    text = _texts(page)

    assert "notification windows draws on this device" in text
    assert "off (the default)" in text


def test_the_settings_page_shows_the_freshness_settings(app) -> None:
    page = SettingsPage(AppConfig(), gateway_name=lambda: "stub", stats=lambda: {})

    text = _texts(page)

    assert "freshness.auto" in text
    assert "reminders.enabled" in text
    assert "saved records are" in text
