"""Configuration loading and validation.

Configuration is data, not code: it lives outside the package, is validated with
explicit schemas, and never contains credentials in the repository.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Literal

import pydantic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

APP_NAME = "ScholarPath"
CONFIG_FILENAME = "config.toml"


class ConfigError(Exception):
    """Raised when configuration cannot be read or fails validation."""


class ProviderProfileConfig(BaseModel):
    """One independently configured provider endpoint (G191).

    A profile carries its own base URL, model chain and keys, so two cloud
    providers can be configured side by side instead of sharing one endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    kind: Literal["openai", "opencode", "stub"] = "openai"
    enabled: bool = True
    # The endpoint serves free models only (or is local). Global free-only
    # routing never leaves these profiles.
    free_only: bool = False
    base_url: str = ""
    model: str = ""
    models: list[str] = []
    api_keys: list[str] = []
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)

    @pydantic.model_validator(mode="after")
    def _check_endpoint(self) -> ProviderProfileConfig:
        if self.kind == "openai" and not self.base_url.strip():
            raise ValueError("gateway.profiles: an 'openai' profile needs base_url.")
        if self.kind == "openai" and not (self.model.strip() or self.models):
            raise ValueError(
                "gateway.profiles: an 'openai' profile needs model or models."
            )
        return self


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["stub", "opencode", "openai"] = "stub"
    # Providers tried after the first one, in order, when the earlier ones
    # cannot answer (rate limited, unreachable).
    fallback_providers: list[str] = []
    model: str = ""
    # Failover chain: tried in order when a model is rate-limited. Empty means
    # "use the provider's own choice, then its free-tier alternatives".
    models: list[str] = []
    timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    retries: int = Field(default=1, ge=0, le=5)
    # How many model/account attempts one turn may make before the app gives
    # up with an honest error.
    failover_attempts: int = Field(default=6, ge=1, le=24)

    # OpenCode adapter options. Leave base_url empty to discover the running
    # background service from its registration file. When base_url is set, the
    # service password must come from OPENCODE_SERVICE_PASSWORD.
    base_url: str = ""
    service_file: str = ""
    location_dir: str = ""

    # OpenAI-compatible adapter options (provider = "openai").
    api_base_url: str = ""
    # The endpoint's own model and chain. When both are empty the endpoint
    # uses "model"/"models" instead - that is the standalone case.
    api_model: str = ""
    api_models: list[str] = []
    # The app's own keys. They live in the user's local config file or in the
    # SCHOLARPATH_API_KEYS environment variable - never in the repository.
    api_keys: list[str] = []
    # Which environment variable may add keys. Provider profiles set their own
    # name so one provider's key is never sent to another endpoint.
    api_keys_env: str = "SCHOLARPATH_API_KEYS"
    # Console keys the app registers with the model service and rotates
    # between when a model quota is exhausted.
    account_keys: list[str] = []
    # Ask the model service to switch account when a model quota is exhausted.
    rotate_credentials: bool = True

    # Named provider profiles (G191). When at least one is enabled they take
    # precedence over provider / fallback_providers: each profile is its own
    # endpoint with its own model chain and keys.
    profiles: list[ProviderProfileConfig] = []
    # Never route to a profile that is not marked free_only.
    free_only: bool = False

    @pydantic.model_validator(mode="after")
    def _check_providers(self) -> GatewayConfig:
        known = {"stub", "opencode", "openai"}
        unknown = [name for name in self.fallback_providers if name not in known]
        if unknown:
            raise ValueError(
                "gateway.fallback_providers contains unknown providers: "
                + ", ".join(sorted(unknown))
            )
        names = [profile.name for profile in self.profiles]
        if len(names) != len(set(names)):
            raise ValueError("gateway.profiles names must be unique.")
        if self.provider == "openai" and not self.api_base_url.strip() and not self.profiles:
            raise ValueError(
                "gateway.api_base_url is required when provider = 'openai'."
            )
        return self


class UIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal["dark", "light", "system"] = "dark"
    window_width: int = Field(default=1100, ge=800, le=4000)
    window_height: int = Field(default=720, ge=600, le=3000)


class McpServerConfig(BaseModel):
    """One configured MCP server (stdio command). Never auto-enabled."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    command: str = Field(min_length=1)
    args: list[str] = []
    enabled: bool = False


class McpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    # Read-only research default (G109): tools not advertising readOnlyHint
    # are refused while this is true.
    read_only: bool = True
    servers: list[McpServerConfig] = []

    @pydantic.field_validator("servers")
    @classmethod
    def _unique_names(cls, value: list[McpServerConfig]) -> list[McpServerConfig]:
        names = [server.name for server in value]
        if len(names) != len(set(names)):
            raise ValueError("MCP server names must be unique")
        return value


class PrivacyConfig(BaseModel):
    """What may leave this device.

    Each switch is about one third party and one kind of data:

    - ``voice_stt``: the microphone clip is sent to Google's speech service to
      be turned into text.
    - ``voice_tts``: the reply text is sent to Microsoft's speech service to
      be turned into audio.
    - ``web_search``: the search question is sent to the web-search service,
      and the pages it returns are fetched.
    - ``chat_profile``: a short summary of the saved profile (degree level,
      GPA and scale, nationality, preferred countries, funding need, language
      scores - never the name, never the documents) is sent with each chat
      message, so the chat does not ask for facts the app already holds.

    All four default to on so the features work without a config-file edit.
    The Settings page states exactly what each one sends and to whom, and its
    toggles save the student's choice back to ``config.toml``.
    """

    model_config = ConfigDict(extra="forbid")

    voice_stt: bool = True
    voice_tts: bool = True
    web_search: bool = True
    chat_profile: bool = True


class SearchConfig(BaseModel):
    """How the web search behaves. The student's own trusted domains."""

    model_config = ConfigDict(extra="forbid")

    # Domains the student trusts (for example a scholarship body that is not
    # a university or a government). Matched exactly, on the registrable
    # domain: "chevening.org" covers "www.chevening.org".
    trusted_domains: list[str] = []


class FreshnessConfig(BaseModel):
    """How often the stored records are checked against their pages (G152).

    The check re-fetches the pages (the guarded fetch, one request per second
    per host), compares the page hash, and re-reads a page that changed. It
    never invents a deadline: a record is expired only when its stored date
    lies before today.
    """

    model_config = ConfigDict(extra="forbid")

    # Check in the background when the app starts and a record is due.
    auto: bool = True
    # How old a record's last check may be before it is due again.
    interval_hours: int = Field(default=24, ge=1, le=720)
    # How many records one run may read (the saved ones are always included).
    max_per_run: int = Field(default=20, ge=1, le=200)


class RemindersConfig(BaseModel):
    """Deadline reminders (G156). Off until the student asks for them."""

    model_config = ConfigDict(extra="forbid")

    # A Windows notification at 30, 14, 7 and 1 days before a saved record's
    # deadline. Nothing leaves the device; the notification is drawn by
    # Windows on this machine.
    enabled: bool = False


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    freshness: FreshnessConfig = Field(default_factory=FreshnessConfig)
    reminders: RemindersConfig = Field(default_factory=RemindersConfig)
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


_PRIVACY_KEYS = ("voice_stt", "voice_tts", "web_search", "chat_profile")
_PRIVACY_HEADER_RE = re.compile(r"^[ \t]*\[privacy\][ \t]*(?:#.*)?$", re.MULTILINE)


def _privacy_block(privacy: PrivacyConfig) -> str:
    lines = ["[privacy]"]
    for key in _PRIVACY_KEYS:
        lines.append(f"{key} = {'true' if getattr(privacy, key) else 'false'}")
    return "\n".join(lines) + "\n"


def _replace_privacy_values(text: str, privacy: PrivacyConfig) -> str:
    """Change only the three privacy values in an existing TOML document."""
    header = _PRIVACY_HEADER_RE.search(text)
    if header is None:
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        return text + _privacy_block(privacy)

    start = header.end()
    prefix = ""
    if start < len(text) and text[start] == "\n":
        start += 1
    else:
        prefix = "\n"
    following = re.search(r"^[ \t]*\[", text[start:], re.MULTILINE)
    end = start + following.start() if following else len(text)
    section = text[start:end]

    missing: list[str] = []
    for key in _PRIVACY_KEYS:
        value = "true" if getattr(privacy, key) else "false"
        pattern = re.compile(
            rf"^([ \t]*{re.escape(key)}[ \t]*=[ \t]*)(true|false)([ \t]*(?:#.*)?)$",
            re.MULTILINE,
        )
        if pattern.search(section):
            section = pattern.sub(
                lambda match, new=value: match.group(1) + new + match.group(3),
                section,
                count=1,
            )
        else:
            missing.append(f"{key} = {value}")
    if missing:
        if section and not section.endswith("\n"):
            section += "\n"
        section += "\n".join(missing) + "\n"
    return text[:start] + prefix + section + text[end:]


def _write_config_atomic(target: Path, text: str) -> None:
    """Write a config update without risking the live file on a failed write."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def save_privacy_config(privacy: PrivacyConfig, path: Path | None = None) -> Path:
    """Save the three privacy switches, preserving everything else in the file.

    The Settings page calls this when a toggle changes. The edit is deliberately
    narrow: comments, gateway keys, trusted domains and every other section stay
    exactly as the student wrote them. The result is parsed and validated before
    it replaces the live file, so a bad edit cannot leave the app unable to
    start. A missing file is created with just the privacy section; defaults
    fill in the rest.
    """
    target = path or config_path()
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration file:\n  {target}\n  {exc}") from exc

    updated = _replace_privacy_values(text, privacy)
    try:
        raw = tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Refusing to save invalid TOML in {target}:\n  {exc}") from exc
    try:
        AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(
            f"Refusing to save an invalid configuration in {target}:\n"
            f"{_format_errors(exc)}"
        ) from exc

    try:
        _write_config_atomic(target, updated)
    except OSError as exc:
        raise ConfigError(f"Cannot write configuration file:\n  {target}\n  {exc}") from exc
    return target
