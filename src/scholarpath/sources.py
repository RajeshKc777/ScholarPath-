""" HTTP(S) page retrieval for scholarship verification.

Fetching is deliberately boring and strict:

- http and https only (no file:, ftp:, data:, no embedded credentials);
- text/html, application/xhtml+xml, text/plain responses only;
- hard byte cap with a "truncated" warning instead of silent trust;
- the page is decoded to plain text locally; scripts and styles are dropped.

The returned text is **untrusted web content**. It must be treated as data
everywhere downstream - never as instructions for the model or the app.
"""

from __future__ import annotations

import hashlib
import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

MAX_BYTES = 2_000_000
DEFAULT_TIMEOUT = 15.0
_ALLOWED_SCHEMES = ("http", "https")
_ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_USER_AGENT = "ScholarPath-AI/0.1 (verification fetch; local-first)"
_HTML_TAGS_TO_SKIP = {"script", "style", "noscript", "template"}


class FetchError(ValueError):
    """Raised with a plain-language reason a page could not be read."""


@dataclass
class Page:
    """A retrieved web page, reduced to text, with provenance attached."""

    requested_url: str
    final_url: str
    title: str
    text: str
    fetched_at: str
    sha256: str
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.text.strip()


class _TextExtractor(HTMLParser):
    """Very small HTML-to-text pass: drop chrome, keep readable content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.chunks: list[str] = []
        self._skipping = 0
        self._in_title = False
        self._block_start = {
            "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
            "section", "article", "header", "footer", "table",
        }

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - stdlib API
        tag = tag.lower()
        if tag in _HTML_TAGS_TO_SKIP:
            self._skipping += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._block_start:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:  # noqa: ANN001 - stdlib API
        tag = tag.lower()
        if tag in _HTML_TAGS_TO_SKIP and self._skipping:
            self._skipping -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._block_start:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:  # noqa: ANN001 - stdlib API
        if self._in_title:
            self.title += data.strip()
        elif not self._skipping:
            self.chunks.append(data)

    def text(self) -> str:
        """Whitespace-collapsed text that still keeps line structure."""
        lines: list[str] = []
        current: list[str] = []
        for chunk in self.chunks:
            if "\n" in chunk:
                current.append(chunk)
                line = "".join(current).split("\n")
                lines.extend(part.strip() for part in line)
                current = []
            else:
                current.append(chunk)
        if current:
            lines.append("".join(current).strip())
        return "\n".join(part for part in lines if part)


def _assert_public_html_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise FetchError(
            f"Only http(s) pages can be read - this link uses '{parts.scheme or 'no'}:'."
        )
    if parts.username or parts.password:
        raise FetchError("Links with embedded credentials are not supported.")
    if not parts.hostname:
        raise FetchError("That link has no host name.")
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except OSError as exc:
        raise FetchError(f"Could not resolve the host '{parts.hostname}': {exc}") from exc
    for info in infos:
        address = info[4][0]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:  # pragma: no cover - getaddrinfo returns IPs
            continue
        # Loopback/private links are allowed (local mirrors, tests, proxies);
        # link-local and unspecified targets never make sense here.
        if parsed.is_link_local or parsed.is_unspecified:
            raise FetchError("That link points to a non-routable address.")


def _decode(body: bytes, charset: str | None) -> str:
    for candidate in (charset, "utf-8", "windows-1252"):
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


def fetch_page(
    url: str, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = MAX_BYTES
) -> Page:
    """Download one page and reduce it to verified-provenance text."""
    _assert_public_html_url(url)

    request = urlrequest.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"}
    )
    try:
        with urlrequest.urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            status = getattr(response, "status", 200)
            content_type = (response.headers.get("Content-Type") or "").split(";")[
                0
            ].strip().lower()
            charset = response.headers.get_content_charset()
            body = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise FetchError(f"The server returned HTTP {exc.code} for that page.") from exc
    except URLError as exc:
        raise FetchError(f"Could not reach that page: {exc.reason}") from exc
    except TimeoutError as exc:  # pragma: no cover - platform differences
        raise FetchError("The page took too long to respond.") from exc

    if not content_type or not any(
        content_type.startswith(allowed) for allowed in _ALLOWED_TYPES
    ):
        raise FetchError(
            f"That link is not a web page (server said '{content_type or 'unknown type'}')."
        )

    warnings: list[str] = []
    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]
        warnings.append(f"page larger than {max_bytes:,} bytes - text truncated")

    decoded = _decode(body, charset)
    extractor = _TextExtractor()
    try:
        extractor.feed(decoded)
        extractor.close()
    except Exception as exc:  # noqa: BLE001 - malformed HTML must not crash
        warnings.append(f"page structure could not be fully parsed ({exc.__class__.__name__})")

    page = Page(
        requested_url=url,
        final_url=final_url,
        title=extractor.title,
        text=extractor.text(),
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        sha256=hashlib.sha256(body).hexdigest(),
        truncated=truncated,
        warnings=warnings,
    )
    if page.empty:
        raise FetchError("No readable text was found on that page.")
    return page
