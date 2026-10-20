"""Page retrieval with verified provenance (Milestone 4)."""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scholarpath.sources import FetchError, fetch_page

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
