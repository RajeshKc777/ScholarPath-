"""Configuration loading and validation.

Configuration is data, not code: it lives outside the package, is validated with
explicit schemas, and never contains credentials in the repository.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

APP_NAME = "ScholarPath"
CONFIG_FILENAME = "config.toml"


class ConfigError(Exception):
    """Raised when configuration cannot be read or fails validation."""


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["stub", "opencode"] = "stub"
    model: str = ""
    timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    retries: int = Field(default=1, ge=0, le=5)

    # OpenCode adapter options. Leave base_url empty to discover the running
    # background service from its registration file. When base_url is set, the
    # service password must come from OPENCODE_SERVICE_PASSWORD.
    base_url: str = ""
    service_file: str = ""
    location_dir: str = ""


class UIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal["dark", "light", "system"] = "dark"
    window_width: int = Field(default=1100, ge=800, le=4000)
    window_height: int = Field(default=720, ge=600, le=3000)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


def app_data_dir() -> Path:
    """Directory for user data, logs, and config - never inside the package."""
    base = os.environ.get("SCHOLARPATH_HOME")
    if base:
        return Path(base)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def config_path() -> Path:
    return app_data_dir() / CONFIG_FILENAME


def template_path() -> Path:
    """The shipped template. Falls back to the repo copy during development."""
    candidates = [
        Path(__file__).resolve().parent / "data" / "config.example.toml",
        Path(__file__).resolve().parents[2] / "config.example.toml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ConfigError(
        "config.example.toml is missing from the installation. "
        "Reinstall the application or restore the template file."
    )


def _format_errors(error: ValidationError) -> str:
    lines: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "config"
        lines.append(f"  {location}: {item['msg']}")
    return "\n".join(lines)


def load_config(path: Path | None = None) -> AppConfig:
    """Load and validate configuration.

    A missing file is not an error: defaults are used so a fresh checkout runs.
    A malformed or invalid file *is* an error - never silently ignored.
    """
    target = path or config_path()
    if not target.exists():
        return AppConfig()

    try:
        raw = tomllib.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration file:\n  {target}\n  {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {target}:\n  {exc}") from exc

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(
            f"Invalid configuration in {target}:\n{_format_errors(exc)}"
        ) from exc


def init_config(path: Path | None = None, overwrite: bool = False) -> Path:
    """Copy the template to the user config location. Returns the written path."""
    target = path or config_path()
    if target.exists() and not overwrite:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template_path().read_text(encoding="utf-8"), encoding="utf-8")
    return target
