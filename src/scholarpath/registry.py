"""The official-portal registry: which sites the catalog is allowed to read.

The registry is **data, not code**. It ships as `sources_registry.toml` inside
the package and is copied to `%APPDATA%\\ScholarPath\\sources_registry.toml`
where the student can edit it. Only the portals listed here are ever crawled.

Each entry names one official body:

- ``name`` - the portal as it is known.
- ``base_url`` - the page the crawl starts from (https only).
- ``country`` - the country the scholarship is for.
- ``trust_level`` - ``official`` (the awarding body's own portal) or
  ``government`` (a ministry or government department portal).
- ``allowed_path_prefixes`` - the URL paths the crawler may read on that
  site. A URL outside these prefixes is never fetched, even when a link to it
  is found.
- ``crawl_depth`` - how many link levels below the start page may be read.

Every entry in the shipped default was checked with the app's own guarded
fetch on the day it was added. A portal that could not be read was left out
rather than shipped as a promise the app cannot keep.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from scholarpath.config import app_data_dir

REGISTRY_FILENAME = "sources_registry.toml"
REGISTRY_VERSION = 1

#: Trust levels the registry understands.
TRUST_LEVELS = ("official", "government")


class RegistryError(ValueError):
    """Raised when the registry file cannot be read or is not valid."""


@dataclass(frozen=True)
class Source:
    """One official portal the catalog may crawl."""

    name: str
    base_url: str
    country: str
    trust_level: str
    allowed_path_prefixes: tuple[str, ...]
    crawl_depth: int = 1
    enabled: bool = True

    @property
    def host(self) -> str:
        return (urlsplit(self.base_url).hostname or "").lower()

    @property
    def site_root(self) -> str:
        """The scheme + host of the portal, e.g. ``https://example.gov``."""
        parts = urlsplit(self.base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def domain(self) -> str:
        """The registrable domain, used as the provider key of a record."""
        host = self.host
        return host[4:] if host.startswith("www.") else host

    def allows_path(self, path: str) -> bool:
        """Is this URL path inside the area this portal may be read in?"""
        if not self.allowed_path_prefixes:
            return False
        lowered = path.casefold()
        for prefix in self.allowed_path_prefixes:
            if lowered.startswith(prefix.casefold()):
                return True
        return False

    def allows_url(self, url: str) -> bool:
        """Is this URL on this portal and inside an allowed path?"""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return False
        if (parts.hostname or "").lower() != self.host:
            return False
        return self.allows_path(parts.path or "/")


def default_registry_path() -> Path:
    """The shipped registry (inside the package)."""
    candidates = [
        Path(__file__).resolve().parent / "data" / REGISTRY_FILENAME,
        Path(__file__).resolve().parents[2] / REGISTRY_FILENAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RegistryError(
        f"{REGISTRY_FILENAME} is missing from the installation. Reinstall the "
        "application or restore the shipped registry file."
    )


def user_registry_path(home: Path | None = None) -> Path:
    """Where the editable copy lives, next to the app's config."""
    return (home or app_data_dir()) / REGISTRY_FILENAME


def _require_str(entry: dict, key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{where}: '{key}' must be a non-empty string.")
    return value.strip()


def parse_registry(text: str) -> list[Source]:
    """Parse and validate registry text. Every problem is named."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RegistryError(f"Invalid TOML in the sources registry: {exc}") from exc

    version = raw.get("version", REGISTRY_VERSION)
    if version != REGISTRY_VERSION:
        raise RegistryError(
            f"Unsupported sources registry version {version!r} "
            f"(this build understands version {REGISTRY_VERSION})."
        )

    entries = raw.get("source")
    if entries is None:
        raise RegistryError("The sources registry has no [[source]] entries.")
    if not isinstance(entries, list) or not entries:
        raise RegistryError("The sources registry has no [[source]] entries.")

    sources: list[Source] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        where = f"source #{index}"
        if not isinstance(entry, dict):
            raise RegistryError(f"{where}: each source must be a table.")

        name = _require_str(entry, "name", where)
        base_url = _require_str(entry, "base_url", where)
        country = _require_str(entry, "country", where)
        trust_level = _require_str(entry, "trust_level", where)
        if trust_level not in TRUST_LEVELS:
            raise RegistryError(
                f"{where} ({name}): 'trust_level' must be one of "
                + ", ".join(TRUST_LEVELS)
                + f" - not {trust_level!r}."
            )

        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise RegistryError(
                f"{where} ({name}): 'base_url' must be a full http(s) address."
            )
        if parts.username or parts.password:
            raise RegistryError(
                f"{where} ({name}): 'base_url' must not carry credentials."
            )

        prefixes = entry.get("allowed_path_prefixes")
        if not isinstance(prefixes, list) or not prefixes:
            raise RegistryError(
                f"{where} ({name}): 'allowed_path_prefixes' must list at least "
                "one path - it is the area the crawler may read."
            )
        cleaned: list[str] = []
        for prefix in prefixes:
            if not isinstance(prefix, str) or not prefix.strip():
                raise RegistryError(
                    f"{where} ({name}): every allowed path prefix must be a "
                    "non-empty string."
                )
            value = prefix.strip()
            if not value.startswith("/"):
                value = "/" + value
            cleaned.append(value)

        depth = entry.get("crawl_depth", 1)
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0 or depth > 5:
            raise RegistryError(
                f"{where} ({name}): 'crawl_depth' must be a whole number "
                "between 0 and 5."
            )

        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise RegistryError(f"{where} ({name}): 'enabled' must be true or false.")

        if base_url in seen:
            raise RegistryError(f"{where} ({name}): '{base_url}' is listed twice.")
        seen.add(base_url)

        sources.append(
            Source(
                name=name,
                base_url=base_url,
                country=country,
                trust_level=trust_level,
                allowed_path_prefixes=tuple(cleaned),
                crawl_depth=depth,
                enabled=enabled,
            )
        )
    return sources


def load_registry(path: Path | None = None) -> list[Source]:
    """Load the registry: the student's copy when it exists, else the default.

    A broken file is an error with a named reason - it is never silently
    replaced by the shipped default, because that would hide the student's
    own edits.
    """
    target = path or user_registry_path()
    if not target.exists():
        target = default_registry_path()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryError(f"Could not read the sources registry:\n  {target}\n  {exc}") from exc
    return parse_registry(text)


def write_user_registry(
    sources: list[Source] | None = None, path: Path | None = None
) -> Path:
    """Write the editable copy of the registry (seeded from the default)."""
    target = path or user_registry_path()
    if target.exists():
        return target
    if sources is None:
        text = default_registry_path().read_text(encoding="utf-8")
    else:
        text = render_registry(sources)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def render_registry(sources: list[Source]) -> str:
    """Render sources back into the registry file format."""
    lines = [
        "# ScholarPath AI - official scholarship portals.",
        "# This is your editable copy. Add, remove or disable entries as you",
        "# like; the app only crawls the portals listed here.",
        "",
        f"version = {REGISTRY_VERSION}",
        "",
    ]
    for source in sources:
        lines.append("[[source]]")
        lines.append(f'name = "{source.name}"')
        lines.append(f'base_url = "{source.base_url}"')
        lines.append(f'country = "{source.country}"')
        lines.append(f'trust_level = "{source.trust_level}"')
        prefixes = ", ".join(f'"{prefix}"' for prefix in source.allowed_path_prefixes)
        lines.append(f"allowed_path_prefixes = [{prefixes}]")
        lines.append(f"crawl_depth = {source.crawl_depth}")
        lines.append(f"enabled = {'true' if source.enabled else 'false'}")
        lines.append("")
    return "\n".join(lines)


def registry_in_use(path: Path | None = None) -> tuple[list[Source], Path, bool]:
    """The sources, the file they came from, and whether it is the user's copy."""
    target = path or user_registry_path()
    if target.exists():
        return parse_registry(target.read_text(encoding="utf-8")), target, True
    return load_registry(), default_registry_path(), False
