"""Crawl discovery: link scoring, caps, noise, and PDFs (G187-G188).

Everything runs against a fake portal on loopback - the suite never touches
the real internet.
"""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from fake_pdf import make_pdf
from scholarpath.crawler import (
    MAX_CRAWL_DEPTH,
    MAX_LINKS_PER_PAGE,
    MIN_INTERVAL_SECONDS,
    Crawler,
    HostThrottle,
)
from scholarpath.discovery import is_noise, page_links, score_link
from scholarpath.registry import Source
from scholarpath.sources import FetchError, Resource, pdf_from_resource

REQUESTS: list[str] = []

ROBOTS = "User-agent: *\nCrawl-delay: 0\n"

BROCHURE = make_pdf(
    "Scholarship brochure\nDeadline: 5 November 2026\nFully funded tuition."
)
SCAN = make_pdf("", blank=True)

INDEX = """<html><head><title>Scholarships</title></head><body>
<a href="/scholarships/login">Login</a>
<a href="/scholarships/apply.html">Apply</a>
<a href="/scholarships/best.html">Fully funded scholarship</a>
<a href="/scholarships/notes.html">Contact us</a>
<a href="/scholarships/cart/checkout">Cart</a>
<a href="/scholarships/archive/2024/old-scholarship.html">Archive</a>
<a href="/scholarships/calendar">Calendar</a>
<a href="/scholarships/brochure.pdf">Scholarship brochure (PDF)</a>
<a href="/scholarships/scan.pdf">Scholarship scan (PDF)</a>
<a href="/scholarships/step-1.html">Scholarship step 1</a>
</body></html>"""

BEST = """<html><head><title>Best scholarship</title></head>
<body><h1>Fully funded scholarship</h1><p>Deadline: 1 May 2027.</p></body></html>"""

APPLY = """<html><head><title>Apply</title></head>
<body><h1>Apply for the scholarship</h1></body></html>"""

PLAIN = "<html><body><p>Nothing about money for study here.</p></body></html>"


def step_page(number: int) -> str:
    return (
        f"<html><head><title>Scholarship step {number}</title></head><body>"
        f'<a href="/scholarships/step-{number + 1}.html">Scholarship step {number + 1}</a>'
        "</body></html>"
    )


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence the test output
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        path = self.path.split("?")[0]
        REQUESTS.append(path)
        if path == "/robots.txt":
            self._send(200, "text/plain; charset=utf-8", ROBOTS.encode())
        elif path in ("/scholarships/", "/scholarships/index.html"):
            self._send(200, "text/html; charset=utf-8", INDEX.encode())
        elif path == "/scholarships/best.html":
            self._send(200, "text/html; charset=utf-8", BEST.encode())
        elif path == "/scholarships/apply.html":
            self._send(200, "text/html; charset=utf-8", APPLY.encode())
        elif path == "/scholarships/notes.html":
            self._send(200, "text/html; charset=utf-8", PLAIN.encode())
        elif path.startswith("/scholarships/step-") and path.endswith(".html"):
            number = path.rsplit("-", 1)[-1].split(".")[0]
            self._send(200, "text/html; charset=utf-8", step_page(int(number)).encode())
        elif path == "/scholarships/brochure.pdf":
            self._send(200, "application/pdf", BROCHURE)
        elif path == "/scholarships/scan.pdf":
            self._send(200, "application/pdf", SCAN)
        elif path in (
            "/scholarships/login",
            "/scholarships/cart/checkout",
            "/scholarships/archive/2024/old-scholarship.html",
            "/scholarships/calendar",
        ):
            # These must never be asked for; if they are, the test sees it.
            self._send(200, "text/html; charset=utf-8", PLAIN.encode())
        else:
            self._send(404, "text/plain", b"missing")

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def clear_requests() -> None:
    REQUESTS.clear()


def make_source(base_url: str, *, depth: int = 1) -> Source:
    return Source(
        name="Fake Portal",
        base_url=f"{base_url}/scholarships/index.html",
        country="Testland",
        trust_level="official",
        allowed_path_prefixes=("/scholarships/",),
        crawl_depth=depth,
    )


def make_crawler(**kwargs) -> Crawler:
    kwargs.setdefault("allow_loopback", True)
    kwargs.setdefault("throttle", HostThrottle(min_interval=0.0))
    return Crawler(**kwargs)


# -- link scoring -----------------------------------------------------------


def test_a_scholarship_link_scores_highest() -> None:
    assert score_link("https://example.gov/scholarships/index.html") >= 3
    assert score_link("https://example.gov/apply") > score_link("https://example.gov/news")


def test_the_task_words_all_score() -> None:
    for path in (
        "/scholarship",
        "/fellowships",
        "/grant",
        "/funding",
        "/bursary",
        "/apply-now",
        "/eligibility",
        "/deadline",
        "/financial-aid",
    ):
        assert score_link(f"https://example.gov{path}") > 0, path


def test_a_link_label_counts_as_well_as_its_path() -> None:
    assert score_link("https://example.gov/node/12", "Apply for the scholarship") >= 3


def test_local_language_words_are_recognised() -> None:
    for path in (
        "/장학금-안내",  # Korean
        "/奨学金",  # Japanese
        "/奖学金",  # Chinese
        "/beasiswa",  # Indonesian
        "/chhatrabritti",  # Nepali, romanised
        "/stipendium",  # German
        "/bourse",  # French
        "/becas",  # Spanish
    ):
        assert score_link(f"https://example.gov{path}") >= 3, path


def test_a_percent_encoded_path_is_scored() -> None:
    # The Korean word for scholarship, percent-encoded, as a real portal links it.
    encoded = "/%EC%9E%A5%ED%95%99%EA%B8%88"
    assert score_link(f"https://example.gov{encoded}") >= 3


def test_a_short_word_does_not_fire_inside_another_word() -> None:
    # "beca" (Spanish for scholarship) must not match "because".
    assert score_link("https://example.gov/because-we-care") == 0
    assert score_link("https://example.gov/beca") >= 3


def test_a_page_with_no_scholarship_words_scores_zero() -> None:
    assert score_link("https://example.gov/about-us") == 0
    assert score_link("https://example.gov/news/2024/03") == 0


# -- noise ------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/login",
        "/signin",
        "/cart",
        "/cart/checkout",
        "/calendar",
        "/news/archive/2024",
        "/tag/funding",
        "/search?q=scholarship",
        "/account/settings",
    ],
)
def test_obvious_non_content_is_noise(path: str) -> None:
    assert is_noise(f"https://example.gov{path}") is True


def test_a_real_scholarship_page_is_not_noise() -> None:
    assert is_noise("https://example.gov/scholarships/apply.html") is False
    assert is_noise("https://example.gov/funding/graduate") is False


# -- PDF links --------------------------------------------------------------


def test_page_links_keep_documents_out_by_default() -> None:
    html = '<a href="/files/brochure.pdf">Brochure</a>'
    urls = [url for url, _label in page_links(html, "https://example.gov/scholarships/")]
    assert not any(url.endswith(".pdf") for url in urls)


def test_page_links_can_keep_pdfs_for_the_crawler() -> None:
    html = '<a href="/files/brochure.pdf">Brochure</a>'
    urls = [
        url
        for url, _label in page_links(
            html, "https://example.gov/scholarships/", allow_pdf=True
        )
    ]
    assert urls == ["https://example.gov/files/brochure.pdf"]


# -- the crawl uses the scores ---------------------------------------------


def test_the_best_scoring_link_is_read_first(base_url: str) -> None:
    result = make_crawler(max_pages=2).crawl(make_source(base_url))
    urls = [page.url for page in result.pages]
    assert urls[1].endswith("/scholarships/best.html")
    assert not any(url.endswith("/apply.html") for url in urls)


def test_obvious_non_content_is_never_requested(base_url: str) -> None:
    make_crawler(max_pages=20).crawl(make_source(base_url, depth=2))
    for path in (
        "/scholarships/login",
        "/scholarships/cart/checkout",
        "/scholarships/archive/2024/old-scholarship.html",
        "/scholarships/calendar",
    ):
        assert path not in REQUESTS, path


def test_a_link_with_no_scholarship_words_is_not_queued() -> None:
    crawler = make_crawler()
    source = Source(
        name="News",
        base_url="https://example.gov/",
        country="Testland",
        trust_level="official",
        allowed_path_prefixes=("/",),
    )
    html = (
        '<a href="/news/2024/story.html">Campus news</a>'
        '<a href="/funding/graduate">Graduate funding</a>'
    )
    seeds = crawler.link_seeds(source, "https://example.gov/", html)
    assert seeds == ["https://example.gov/funding/graduate"]


# -- caps -------------------------------------------------------------------


def test_the_registry_cannot_make_a_run_deeper_than_the_cap(base_url: str) -> None:
    result = make_crawler(max_pages=30).crawl(make_source(base_url, depth=5))
    urls = {page.url for page in result.pages}
    assert MAX_CRAWL_DEPTH == 3
    assert f"{base_url}/scholarships/step-3.html" in urls
    assert f"{base_url}/scholarships/step-4.html" not in urls
    assert "/scholarships/step-4.html" not in REQUESTS


def test_a_page_cannot_flood_the_queue() -> None:
    links = "".join(
        f'<a href="/scholarships/{index}-scholarship.html">Scholarship {index}</a>'
        for index in range(MAX_LINKS_PER_PAGE + 40)
    )
    crawler = make_crawler()
    source = Source(
        name="Flood",
        base_url="https://example.gov/scholarships/",
        country="Testland",
        trust_level="official",
        allowed_path_prefixes=("/scholarships/",),
    )
    seeds = crawler.link_seeds(source, "https://example.gov/scholarships/", links)
    assert len(seeds) == MAX_LINKS_PER_PAGE


def test_the_pace_is_still_one_second_per_host() -> None:
    assert MIN_INTERVAL_SECONDS == 1.0


# -- PDFs -------------------------------------------------------------------


def test_a_pdf_is_read_and_keeps_its_address_and_hash(base_url: str) -> None:
    result = make_crawler(max_pages=30).crawl(make_source(base_url))
    pdf_pages = [page for page in result.pages if page.kind == "pdf"]
    brochure = next(page for page in pdf_pages if page.url.endswith("brochure.pdf"))
    assert "Fully funded tuition" in brochure.text
    assert brochure.title  # the file name, since the PDF has no title metadata
    assert brochure.sha256 == hashlib.sha256(BROCHURE).hexdigest()
    assert any("PDF" in warning for warning in brochure.warnings)


def test_a_scanned_pdf_is_refused_with_a_reason(base_url: str) -> None:
    result = make_crawler(max_pages=30).crawl(make_source(base_url))
    assert not any(page.url.endswith("scan.pdf") for page in result.pages)
    assert any("scan.pdf" in problem and "no text layer" in problem for problem in result.errors)


def test_a_pdf_over_the_size_cap_is_refused() -> None:
    resource = Resource(
        requested_url="https://example.gov/big.pdf",
        final_url="https://example.gov/big.pdf",
        status=200,
        content_type="application/pdf",
        charset=None,
        body=b"x" * 100,
    )
    with pytest.raises(FetchError, match="larger than"):
        pdf_from_resource(resource, max_bytes=10)


def test_a_file_that_is_not_really_a_pdf_is_refused() -> None:
    resource = Resource(
        requested_url="https://example.gov/fake.pdf",
        final_url="https://example.gov/fake.pdf",
        status=200,
        content_type="application/pdf",
        charset=None,
        body=b"<html>not a pdf at all</html>",
    )
    with pytest.raises(FetchError, match="could not be read as a PDF"):
        pdf_from_resource(resource)
