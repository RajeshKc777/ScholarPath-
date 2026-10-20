"""Configuration loading must be strict: bad values fail loudly, never silently."""

from __future__ import annotations

from pathlib import Path

import pytest

from scholarpath.config import (
    AppConfig,
    ConfigError,
    app_data_dir,
    config_path,
    init_config,
    load_config,
)


def test_missing_file_uses_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "absent.toml")

    assert isinstance(config, AppConfig)
    assert config.gateway.provider == "stub"
    assert config.ui.window_width == 1100


def test_valid_file_is_parsed(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'log_level = "DEBUG"\n\n'
        '[gateway]\nprovider = "stub"\nmodel = "stub/test"\ntimeout_seconds = 12.5\n'
        '\n[ui]\ntheme = "light"\nwindow_height = 800\n',
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.gateway.model == "stub/test"
    assert config.gateway.timeout_seconds == 12.5
    assert config.ui.theme == "light"
    assert config.ui.window_height == 800
    assert config.log_level == "DEBUG"


def test_invalid_value_names_the_field(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[gateway]\ntimeout_seconds = 0\n", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert "timeout_seconds" in str(excinfo.value)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[gateway]\nbogus_setting = 1\n", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert "bogus_setting" in str(excinfo.value)


def test_unknown_provider_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[gateway]\nprovider = "magic"\n', encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert "provider" in str(excinfo.value)


def test_broken_toml_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[gateway\nprovider = 'stub'\n", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert "Invalid TOML" in str(excinfo.value)


def test_scholarpath_home_overrides_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHOLARPATH_HOME", str(tmp_path / "home"))

    assert app_data_dir() == tmp_path / "home"
    assert config_path() == tmp_path / "home" / "config.toml"


def test_init_config_writes_template_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHOLARPATH_HOME", str(tmp_path / "home"))

    written = init_config()
    assert written.is_file()
    assert "[gateway]" in written.read_text(encoding="utf-8")

    written.write_text("# user edits\n", encoding="utf-8")
    init_config()
    assert written.read_text(encoding="utf-8") == "# user edits\n"

    init_config(overwrite=True)
    assert "[gateway]" in written.read_text(encoding="utf-8")
