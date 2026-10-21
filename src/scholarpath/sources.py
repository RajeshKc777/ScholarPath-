""" HTTP(S) page retrieval for scholarship verification.

Fetching is deliberately boring and strict:

- http and https only (no file:, ftp:, data:, no embedded credentials);
- text/html, application/xhtml+xml, text/plain responses only;
- hard byte cap with a "truncated" warning instead of silent trust;
- the page is decoded to plain text locally; scripts and styles are dropped;
- **SSRF hardening**: the host is resolved *before* connecting and every
  resolved address must be a public one. Loopback, private, link-local,
  carrier-grade NAT, multicast and cloud-metadata addresses are refused with
  a typed error, on the first request *and* on every redirect hop. The
  address that was checked is the address that is connected to, so a DNS
  answer that changes between the check and the connection cannot smuggle the
  request onto the local network.

The returned text is **untrusted web content**. It must be treated as data
everywhere downstream - never as instructions for the model or the app.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import socket
import ssl
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


class BlockedRequest(FetchError):
    """The address is not allowed: it points inside a private network."""


# Networks that must never be reached from a page fetch. Loopback is handled
# separately: it is only used by the local test server, and even then only
# when the caller explicitly asks for it.
_BLOCKED_V4 = tuple(
    ipaddress.ip_network(network)
    for network in (
        "0.0.0.0/8",          # "this" network
        "10.0.0.0/8",         # private
        "100.64.0.0/10",      # carrier-grade NAT
        "169.254.0.0/16",     # link-local (and cloud metadata)
        "172.16.0.0/12",      # private
        "192.0.0.0/24",       # IETF protocol assignments
        "192.0.2.0/24",       # documentation (TEST-NET-1)
        "192.168.0.0/16",     # private
        "198.18.0.0/15",      # benchmarking
        "198.51.100.0/24",    # documentation (TEST-NET-2)
        "203.0.113.0/24",     # documentation (TEST-NET-3)
        "224.0.0.0/4",        # multicast
        "240.0.0.0/4",        # reserved
    )
)
_BLOCKED_V6 = tuple(
    ipaddress.ip_network(network)
    for network in (
        "::/128",             # unspecified
        "fc00::/7",           # unique local
        "fe80::/10",          # link-local
        "ff00::/8",           # multicast
        "2001:db8::/32",      # documentation
    )
)
# Well-known instance metadata endpoints.
_METADATA_ADDRESSES = {
    "169.254.169.254",     # AWS, Azure, GCP
    "169.254.170.2",       # AWS ECS task metadata
    "100.100.100.200",     # Alibaba Cloud
    "192.0.0.192",         # Oracle Cloud
    "fd00:ec2::254",       # AWS IPv6 metadata
}


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


def _address_reason(
    address: ipaddress._BaseAddress, allow_loopback: bool = False
) -> str | None:
    """Why this address must not be reached (None when it is a public one)."""
    text = address.compressed.lower()
    if text in _METADATA_ADDRESSES:
        return "it is a cloud instance metadata address"
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped
        if mapped is not None:
            return _address_reason(mapped, allow_loopback)
        if address.is_loopback:
            return None if allow_loopback else "it is a loopback address"
        if any(address in network for network in _BLOCKED_V6):
            return "it is a local or reserved IPv6 address"
        return None
    if address.is_loopback:
        return None if allow_loopback else "it is a loopback address"
    if any(address in network for network in _BLOCKED_V4):
        return "it is a local or reserved address"
    return None


def _resolve(host: str) -> list[ipaddress._BaseAddress]:
    """Resolve a host name to its addresses."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve the host '{host}': {exc}") from exc
    except OSError as exc:
        raise FetchError(f"Could not resolve the host '{host}': {exc}") from exc
    addresses: list[ipaddress._BaseAddress] = []
    for info in infos:
        raw = info[4][0]
        try:
            addresses.append(ipaddress.ip_address(raw))
        except ValueError:  # pragma: no cover - getaddrinfo returns addresses
            continue
    if not addresses:
        raise FetchError(f"Could not resolve the host '{host}'.")
    return addresses


def _check_addresses(
    host: str,
    addresses: list[ipaddress._BaseAddress],
    allow_loopback: bool = False,
) -> str:
    """Raise when any resolved address is not a public one."""
    for address in addresses:
        reason = _address_reason(address, allow_loopback)
        if reason is not None:
            raise BlockedRequest(
                f"That link points to an address that cannot be read safely "
                f"({reason})."
            )
    return addresses[0].compressed


def _hostname_of(request: urlrequest.Request) -> str:
    return (urlsplit(request.full_url).hostname or "").lower()


def _assert_public_html_url(url: str, allow_loopback: bool = False) -> str:
    """Validate a URL and return the address that must be connected to.

    The name is resolved here and the checked address is the one that is
    connected to, so the answer cannot change underneath the request.
    """
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise FetchError(
            f"Only http(s) pages can be read - this link uses '{parts.scheme or 'no'}:'."
        )
    if parts.username or parts.password:
        raise FetchError("Links with embedded credentials are not supported.")
    if not parts.hostname:
        raise FetchError("That link has no host name.")
    addresses = _resolve(parts.hostname)
    return _check_addresses(parts.hostname, addresses, allow_loopback)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Connects to the address that was checked, not to a fresh DNS answer."""

    def __init__(self, host: str, *, pinned_ip: str | None = None, **kwargs) -> None:
        self._pinned_ip = pinned_ip
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        if not self._pinned_ip:
            super().connect()
            return
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )
        if self._tunnel_host:  # pragma: no cover - proxies are not used here
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS variant: the certificate is still checked against the host name."""

    def __init__(self, host: str, *, pinned_ip: str | None = None, **kwargs) -> None:
        self._pinned_ip = pinned_ip
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        if not self._pinned_ip:
            super().connect()
            return
        raw = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )
        if self._tunnel_host:  # pragma: no cover - proxies are not used here
            self._tunnel()
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class _PinnedHTTPHandler(urlrequest.HTTPHandler):
    handler_order = 100

    def __init__(self, pins: dict[str, str]) -> None:
        self._pins = pins
        super().__init__()

    def http_open(self, req: urlrequest.Request):  # noqa: ANN001 - stdlib API
        return self.do_open(
            _PinnedHTTPConnection, req, pinned_ip=self._pins.get(_hostname_of(req))
        )


class _PinnedHTTPSHandler(urlrequest.HTTPSHandler):
    handler_order = 100

    def __init__(self, pins: dict[str, str], context: ssl.SSLContext | None = None) -> None:
        self._pins = pins
        super().__init__(debuglevel=0, context=context)

    def https_open(self, req: urlrequest.Request):  # noqa: ANN001 - stdlib API
        return self.do_open(
            _PinnedHTTPSConnection,
            req,
            context=self._context,
            pinned_ip=self._pins.get(_hostname_of(req)),
        )


class _ValidatingRedirectHandler(urlrequest.HTTPRedirectHandler):
    """Every redirect hop is checked and pinned again, like the first request."""

    handler_order = 499

    def __init__(self, pins: dict[str, str], allow_loopback: bool = False) -> None:
        self._pins = pins
        self._allow_loopback = allow_loopback
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        host = (urlsplit(newurl).hostname or "").lower()
        addresses = _resolve(host)
        pinned = _check_addresses(host, addresses, self._allow_loopback)
        if pinned:
            self._pins[host] = pinned
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener(pins: dict[str, str], allow_loopback: bool) -> urlrequest.OpenerDirector:
    """An opener that connects to the checked addresses and re-checks hops."""
    context = ssl.create_default_context()
    return urlrequest.build_opener(
        _PinnedHTTPSHandler(pins, context),
        _PinnedHTTPHandler(pins),
        _ValidatingRedirectHandler(pins, allow_loopback),
    )


def _decode(body: bytes, charset: str | None) -> str:
    for candidate in (charset, "utf-8", "windows-1252"):
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


def _download(
    url: str, timeout: float, max_bytes: int, allow_loopback: bool = False
) -> tuple[bytes, str, str | None]:
    """Fetch one URL under the app's strict rules.

    Returns (body, final_url, charset). The body may be one byte longer than
    `max_bytes` so the caller can detect truncation.
    """
    pins: dict[str, str] = {}
    pinned = _assert_public_html_url(url, allow_loopback=allow_loopback)
    if pinned:
        pins[(urlsplit(url).hostname or "").lower()] = pinned

    request = urlrequest.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"}
    )
    opener = _build_opener(pins, allow_loopback)
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
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
    return body, final_url, charset


def fetch_html(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = MAX_BYTES,
    allow_loopback: bool = False,
) -> tuple[str, str]:
    """Download one page and return (html, final_url) for link discovery.

    The HTML is untrusted web content: callers must treat it as data only.
    """
    body, final_url, charset = _download(url, timeout, max_bytes, allow_loopback)
    if len(body) > max_bytes:
        body = body[:max_bytes]
    return _decode(body, charset), final_url


def fetch_page(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = MAX_BYTES,
    allow_loopback: bool = False,
) -> Page:
    """Download one page and reduce it to verified-provenance text."""
    body, final_url, charset = _download(url, timeout, max_bytes, allow_loopback)

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
