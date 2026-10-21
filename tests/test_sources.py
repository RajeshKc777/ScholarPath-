"""Page retrieval with verified provenance (Milestone 4)."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scholarpath import sources
from scholarpath.sources import BlockedRequest, FetchError
from scholarpath.sources import fetch_page as _fetch_page


def fetch_page(url: str, **kwargs) -> object:
    """The test server is on loopback, which only this flag allows."""
    return _fetch_page(url, allow_loopback=True, **kwargs)

HTML_OK = b"""<!DOCTYPE html>
<html><head><title>Chevening-style Test Scholarship</title>
<script>window.tracker = "IGNORED";</script>
<style>.a { color: red; }</style></head>
<body><h1>Test Scholarship 2025</h1>
<p>Funded by the Test Academy. Deadline: 5 November 2025.</p>
<p>Host country: United Kingdom. Fully funded tuition and a monthly stipend of GBP 1,200.</p>
</body></html>"""

PLAIN_OK = b"Plain text scholarship page. Deadline: 1 March 2026."
REDIRECT_TARGET = HTML_OK


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence
        return

    def do_GET(self) -> None:
        route = self.path.split("?")[0]
        if route == "/ok":
            self._send(200, "text/html; charset=utf-8", HTML_OK)
        elif route == "/plain":
            self._send(200, "text/plain; charset=utf-8", PLAIN_OK)
        elif route == "/redirect":
            self._redirect("/ok")
        elif route == "/redirect-metadata":
            self._redirect("http://169.254.169.254/latest/meta-data/")
        elif route == "/notfound":
            self._send(404, "text/html", b"<html><body>nope</body></html>")
        elif route == "/binary":
            self._send(200, "application/octet-stream", b"\x00\x01\x02")
        elif route == "/big":
            self._send(200, "text/html", b"<html><body>" + b"x" * 3_000_000 + b"</body></html>")
        elif route == "/empty":
            self._send(200, "text/html", b"<html><body></body></html>")
        else:
            self._send(404, "text/plain", b"missing")

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture(scope="module")
def base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


def test_fetch_html_extracts_text_title_and_hash(base_url: str) -> None:
    page = fetch_page(f"{base_url}/ok")
    assert page.title == "Chevening-style Test Scholarship"
    assert "Test Scholarship 2025" in page.text
    assert "Deadline: 5 November 2025" in page.text
    assert "IGNORED" not in page.text  # scripts dropped
    assert "color: red" not in page.text  # styles dropped
    assert page.empty is False
    assert page.sha256 == hashlib.sha256(HTML_OK).hexdigest()
    assert page.truncated is False


def test_fetch_plain_text(base_url: str) -> None:
    page = fetch_page(f"{base_url}/plain")
    assert page.text.startswith("Plain text scholarship page")


def test_fetch_follows_redirect_and_reports_final_url(base_url: str) -> None:
    page = fetch_page(f"{base_url}/redirect")
    assert page.final_url == f"{base_url}/ok"
    assert page.requested_url.startswith(f"{base_url}/redirect")


def test_wrong_content_type_is_rejected(base_url: str) -> None:
    with pytest.raises(FetchError) as excinfo:
        fetch_page(f"{base_url}/binary")
    assert "not a web page" in str(excinfo.value)


def test_http_error_maps_to_friendly_message(base_url: str) -> None:
    with pytest.raises(FetchError) as excinfo:
        fetch_page(f"{base_url}/notfound")
    assert "HTTP 404" in str(excinfo.value)


def test_non_http_schemes_are_refused() -> None:
    with pytest.raises(FetchError):
        fetch_page("file:///C:/Windows/notepad.exe")
    with pytest.raises(FetchError):
        fetch_page("ftp://example.org/file.pdf")
    with pytest.raises(FetchError):
        fetch_page("https://user:secret@example.org/page")


def test_unresolvable_host_is_refused() -> None:
    with pytest.raises(FetchError):
        fetch_page("https://scholarpath.invalid-host.example")


def test_oversized_page_is_truncated_not_trusted(base_url: str) -> None:
    page = fetch_page(f"{base_url}/big", max_bytes=100_000)
    assert page.truncated is True
    assert len(page.text.encode("utf-8")) <= 100_000
    body_start = b"<html><body>" + b"x" * (100_000 - len(b"<html><body>"))
    assert page.sha256 == hashlib.sha256(body_start).hexdigest()


def test_empty_page_is_refused(base_url: str) -> None:
    with pytest.raises(FetchError):
        fetch_page(f"{base_url}/empty")


# -- SSRF hardening -------------------------------------------------------

def test_loopback_is_refused_by_default(base_url: str) -> None:
    with pytest.raises(BlockedRequest) as excinfo:
        _fetch_page(f"{base_url}/ok")
    assert "loopback" in str(excinfo.value)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",          # loopback
        "127.9.9.9",         # loopback range
        "10.0.0.1",          # private
        "172.16.5.4",        # private
        "192.168.1.10",      # private
        "169.254.1.1",       # link-local
        "169.254.169.254",   # cloud metadata
        "169.254.170.2",     # ECS task metadata
        "100.100.100.200",   # Alibaba metadata
        "0.0.0.0",           # "this" network
        "[::1]",             # IPv6 loopback
        "[fc00::1]",         # IPv6 unique local
        "[fe80::1]",         # IPv6 link-local
        "[::ffff:127.0.0.1]",  # IPv4-mapped loopback
    ],
)
def test_private_and_metadata_addresses_are_refused(host: str) -> None:
    with pytest.raises(BlockedRequest):
        _fetch_page(f"http://{host}/page")


def test_a_host_that_resolves_to_a_private_address_is_refused(monkeypatch) -> None:
    """A public-looking name that points home is refused."""

    def fake_getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))]

    monkeypatch.setattr(sources.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(BlockedRequest):
        _fetch_page("https://sneaky.example/page")


def test_a_redirect_to_a_blocked_address_is_refused(base_url: str) -> None:
    """Every hop is checked, not only the first request."""
    with pytest.raises(BlockedRequest):
        fetch_page(f"{base_url}/redirect-metadata")


def test_the_checked_address_is_the_one_that_is_used(monkeypatch, base_url: str) -> None:
    """DNS cannot change between the check and the connection (rebinding)."""
    real_getaddrinfo = socket.getaddrinfo
    answers: list[str] = []

    def fake_getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001
        if host == "localhost":
            answers.append(host)
            if len(answers) == 1:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
            # A second, hostile answer for the same name: it must never be used.
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))]
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(sources.socket, "getaddrinfo", fake_getaddrinfo)
    port = base_url.rsplit(":", 1)[1]
    page = _fetch_page(f"http://localhost:{port}/ok", allow_loopback=True)
    assert "Test Scholarship 2025" in page.text
    assert answers == ["localhost"], "the name must be resolved exactly once"


def test_the_blocked_error_is_a_typed_fetch_error() -> None:
    assert issubclass(BlockedRequest, FetchError)
    with pytest.raises(FetchError):
        _fetch_page("http://10.0.0.1/page")


def test_loopback_is_only_allowed_when_asked_for(base_url: str) -> None:
    """The test escape hatch is narrow: loopback yes, private never."""
    with pytest.raises(BlockedRequest):
        _fetch_page("http://10.0.0.1/page", allow_loopback=True)
    with pytest.raises(BlockedRequest):
        _fetch_page("http://169.254.169.254/page", allow_loopback=True)


def test_address_policy_covers_ipv4_and_ipv6() -> None:
    assert sources._address_reason(ipaddress.ip_address("10.0.0.1"))
    assert sources._address_reason(ipaddress.ip_address("::1"))
    assert sources._address_reason(ipaddress.ip_address("::ffff:10.0.0.1"))
    assert sources._address_reason(ipaddress.ip_address("169.254.169.254"))
    assert sources._address_reason(ipaddress.ip_address("8.8.8.8")) is None
    assert sources._address_reason(ipaddress.ip_address("2606:4700::1111")) is None
