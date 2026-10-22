"""The privacy switches, the new sections, and what the Settings page says (G159, G171).

Every switch is on by default, each feature is gated on its own switch, and the
Settings page names the third party and the data for each one. Changing a switch
saves the choice back to config.toml without disturbing the rest of the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import scholarpath.config as config_module
from scholarpath.config import (
    AppConfig,
    ConfigError,
    FreshnessConfig,
    PrivacyConfig,
    RemindersConfig,
    load_config,
    save_privacy_config,
)
from scholarpath.ui.settings_page import SettingsPage


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# -- the switches (G159) ------------------------------------------------------


def test_every_privacy_switch_is_on_by_default() -> None:
    privacy = AppConfig().privacy
    assert privacy.voice_stt is True
    assert privacy.voice_tts is True
    assert privacy.web_search is True


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
    assert "voice input" in text
    assert "spoken replies" in text
    assert "web search" in text
    assert "profile context" in text
    assert "never your name" in text
    assert set(page._privacy_rows) == {
        "voice_stt",
        "voice_tts",
        "web_search",
        "chat_profile",
    }
    assert all(row.toggle.isChecked() for row in page._privacy_rows.values())


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


# -- saving the switches from the page (G171) ---------------------------------


def _privacy_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        "# keep this comment\n"
        'log_level = "INFO"\n'
        "\n"
        "[privacy]\n"
        "# the student's own note\n"
        "voice_stt = true  # keep the inline comment\n"
        "voice_tts = true\n"
        "web_search = true\n"
        "\n"
        "[search]\n"
        'trusted_domains = ["chevening.org"]\n',
        encoding="utf-8",
    )
    return path


def _privacy_page(app, path: Path) -> SettingsPage:
    return SettingsPage(
        AppConfig(
            privacy=PrivacyConfig(
                voice_stt=True, voice_tts=True, web_search=True
            )
        ),
        gateway_name=lambda: "stub",
        stats=lambda: {},
        config_file=path,
    )


def test_a_toggle_saves_the_value_and_emits_once(app, tmp_path: Path) -> None:
    path = _privacy_file(tmp_path)
    page = _privacy_page(app, path)
    fired: list[bool] = []
    page.privacy_changed.connect(lambda: fired.append(True))

    page._privacy_rows["voice_stt"].toggle.click()

    assert page._config.privacy.voice_stt is False
    assert load_config(path).privacy.voice_stt is False
    assert fired == [True]
    assert "saved" in page._privacy_saved.text().casefold()


def test_saving_preserves_comments_and_unrelated_settings(tmp_path: Path) -> None:
    path = _privacy_file(tmp_path)

    save_privacy_config(
        PrivacyConfig(voice_stt=False, voice_tts=True, web_search=False),
        path,
    )

    text = path.read_text(encoding="utf-8")
    assert "# keep this comment" in text
    assert "# the student's own note" in text
    assert "voice_stt = false  # keep the inline comment" in text
    assert "voice_tts = true" in text
    assert "web_search = false" in text
    assert 'trusted_domains = ["chevening.org"]' in text

    loaded = load_config(path)
    assert loaded.privacy.voice_stt is False
    assert loaded.privacy.voice_tts is True
    assert loaded.privacy.web_search is False
    assert loaded.log_level == "INFO"
    assert loaded.search.trusted_domains == ["chevening.org"]


def test_a_missing_config_file_is_created_with_the_privacy_choices(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing" / "config.toml"

    save_privacy_config(
        PrivacyConfig(voice_stt=False, voice_tts=True, web_search=False),
        path,
    )

    loaded = load_config(path)
    assert loaded.privacy.voice_stt is False
    assert loaded.privacy.voice_tts is True
    assert loaded.privacy.web_search is False


def test_a_failed_write_leaves_the_live_file_untouched(
    tmp_path: Path, monkeypatch
) -> None:
    path = _privacy_file(tmp_path)
    before = path.read_text(encoding="utf-8")

    def fail(*_args, **_kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(config_module, "_write_config_atomic", fail)

    with pytest.raises(ConfigError):
        save_privacy_config(
            PrivacyConfig(voice_stt=False, voice_tts=False, web_search=False),
            path,
        )

    assert path.read_text(encoding="utf-8") == before


def test_a_failed_save_reverts_the_toggle_and_says_so(
    app, tmp_path: Path, monkeypatch
) -> None:
    path = _privacy_file(tmp_path)
    page = _privacy_page(app, path)

    def fail(*_args, **_kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("scholarpath.ui.settings_page.save_privacy_config", fail)

    page._privacy_rows["web_search"].toggle.click()

    assert page._config.privacy.web_search is True
    assert page._privacy_rows["web_search"].toggle.isChecked()
    assert "could not save" in page._privacy_saved.text().casefold()
