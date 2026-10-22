"""The crawler: sitemaps, feeds, robots.txt, redirects, 304 and pacing.

Everything runs against a fake HTTP server on loopback - the suite never
touches the real internet.
"""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from fake_pdf import make_pdf
from scholarpath.crawler import (
    MIN_INTERVAL_SECONDS,
    Crawler,
    HostThrottle,
    RobotsRules,
    feed_urls,
    sitemap_files,
    sitemap_urls,
)
from scholarpath.registry import Source

REQUESTS: list[tuple[str, dict[str, str]]] = []

ROBOTS = """User-agent: *
Disallow: /scholarships/blocked/
Crawl-delay: 0
"""

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{base}/sitemap-child.xml</loc></sitemap>
</sitemapindex>"""

SITEMAP_CHILD = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/scholarships/from-sitemap.html</loc></url>
  <url><loc>{base}/private/never.html</loc></url>
  <url><loc>{base}/scholarships/blocked/secret.html</loc></url>
</urlset>"""

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test portal</title>
  <item><title>From the feed</title><link>{base}/scholarships/from-feed.html</link></item>
  <item><title>Off site</title><link>https://example.com/scholarships/nope.html</link></item>
</channel></rss>"""

INDEX = """<html><head><title>Scholarships</title>
<link rel="alternate" type="application/rss+xml" href="{base}/feed.xml">
</head><body>
<h1>Scholarships at the test portal</h1>
<a href="/scholarships/apply.html">Apply for the scholarship</a>
<a href="/scholarships/blocked/secret.html">Blocked scholarship</a>
<a href="/scholarships/poster">Scholarship poster</a>
<a href="/scholarships/file.pdf">Scholarship brochure (PDF)</a>
<a href="https://example.com/scholarships/elsewhere.html">Off-site scholarship</a>
<a href="/scholarships/about.html">About us</a>
<a href="/scholarships/redirect-scholarship">Scholarship redirect</a>
</body></html>"""

PAGE = """<html><head><title>Apply for the scholarship</title></head>
<body><h1>Apply for the scholarship</h1>
<p>Deadline: 5 November 2026. Fully funded tuition.</p>
</body></html>"""

PLAIN_PAGE = """<html><head><title>Another scholarship</title></head>
<body><h1>Another scholarship</h1><p>Deadline: 1 March 2027.</p></body></html>"""

#: A PDF the portal publishes, with a real text layer.
BROCHURE_PDF = make_pdf(
    "Scholarship brochure\nDeadline: 5 November 2026\nFully funded tuition."
)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence the test output
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        path = self.path.split("?")[0]
        REQUESTS.append((path, {key.lower(): value for key, value in self.headers.items()}))
        base = f"http://127.0.0.1:{self.server.server_port}"

        if path == "/robots.txt":
            self._send(200, "text/plain; charset=utf-8", ROBOTS.encode())
        elif path == "/sitemap.xml":
            self._send(200, "application/xml; charset=utf-8", SITEMAP_INDEX.format(base=base).encode())
        elif path == "/sitemap-child.xml":
            self._send(200, "application/xml; charset=utf-8", SITEMAP_CHILD.format(base=base).encode())
        elif path == "/feed.xml":
            self._send(200, "application/rss+xml; charset=utf-8", FEED.format(base=base).encode())
        elif path in ("/scholarships/", "/scholarships/index.html"):
            self._send(200, "text/html; charset=utf-8", INDEX.format(base=base).encode())
        elif path == "/scholarships/apply.html":
            self._send(200, "text/html; charset=utf-8", PAGE.encode())
        elif path in ("/scholarships/from-sitemap.html", "/scholarships/from-feed.html"):
            self._send(200, "text/html; charset=utf-8", PLAIN_PAGE.encode())
        elif path == "/scholarships/about.html":
            self._send(200, "text/html; charset=utf-8", b"<html><body>About us</body></html>")
        elif path == "/scholarships/redirect-scholarship":
            self.send_response(302)
            self.send_header("Location", "/scholarships/apply.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/scholarships/poster":
            self._send(200, "application/octet-stream", b"\x00\x01\x02")
        elif path == "/scholarships/file.pdf":
            self._send(200, "application/pdf", BROCHURE_PDF)
        elif path == "/scholarships/etag-scholarship.html":
            if self.headers.get("If-None-Match") == '"v1"':
                self.send_response(304)
                self.send_header("ETag", '"v1"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("ETag", '"v1"')
            body = PAGE.encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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


def make_source(base_url: str, *, depth: int = 1, name: str = "Test Portal") -> Source:
    return Source(
        name=name,
        base_url=f"{base_url}/scholarships/index.html",
        country="Testland",
        trust_level="official",
        allowed_path_prefixes=("/scholarships/",),
        crawl_depth=depth,
    )


def make_crawler(**kwargs) -> Crawler:
    """A crawler that paces itself without real waiting, on loopback only."""
    kwargs.setdefault("allow_loopback", True)
    kwargs.setdefault("throttle", HostThrottle(min_interval=0.0))
    return Crawler(**kwargs)


def requested_paths() -> list[str]:
    return [path for path, _headers in REQUESTS]


# -- robots.txt ------------------------------------------------------------


def test_robots_rules_are_read_for_our_agent() -> None:
    rules = RobotsRules.parse(ROBOTS)
    assert rules.allows("/scholarships/apply.html") is True
    assert rules.allows("/scholarships/blocked/secret.html") is False


def test_robots_longest_match_wins_and_allow_wins_ties() -> None:
    rules = RobotsRules.parse(
        "User-agent: *\n"
        "Disallow: /scholarships/\n"
        "Allow: /scholarships/public/\n"
        "Disallow: /scholarships/public/private/\n"
    )
    assert rules.allows("/scholarships/other.html") is False
    assert rules.allows("/scholarships/public/page.html") is True
    assert rules.allows("/scholarships/public/private/page.html") is False

    tie = RobotsRules.parse(
        "User-agent: *\nDisallow: /page\nAllow: /page\n"
    )
    assert tie.allows("/page") is True


def test_robots_wildcards_are_understood() -> None:
    rules = RobotsRules.parse("User-agent: *\nDisallow: /*.pdf$\n")
    assert rules.allows("/scholarships/file.pdf") is False
    assert rules.allows("/scholarships/file.pdf?x=1") is True
    assert rules.allows("/scholarships/page.html") is True


def test_robots_can_name_our_agent() -> None:
    text = (
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: ScholarPath\nDisallow: /private/\n"
    )
    rules = RobotsRules.parse(text)
    assert rules.allows("/scholarships/page.html") is True
    assert rules.allows("/private/page.html") is False


def test_an_empty_disallow_forbids_nothing() -> None:
    rules = RobotsRules.parse("User-agent: *\nDisallow:\n")
    assert rules.allows("/anything") is True


def test_robots_crawl_delay_is_read() -> None:
    rules = RobotsRules.parse("User-agent: *\nCrawl-delay: 3\n")
    assert rules.crawl_delay == 3.0


# -- sitemaps and feeds ----------------------------------------------------


def test_sitemap_urlset_is_parsed() -> None:
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.gov/a</loc></url>
      <url><loc>https://example.gov/b</loc></url>
    </urlset>"""
    assert sitemap_urls(xml) == ["https://example.gov/a", "https://example.gov/b"]


def test_sitemap_index_is_parsed_as_files() -> None:
    xml = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.gov/one.xml</loc></sitemap>
      <sitemap><loc>https://example.gov/two.xml</loc></sitemap>
    </sitemapindex>"""
    assert sitemap_files(xml) == ["https://example.gov/one.xml", "https://example.gov/two.xml"]
    assert sitemap_urls(xml) == []


def test_rss_links_are_parsed() -> None:
    xml = """<rss version="2.0"><channel>
      <item><title>One</title><link>https://example.gov/one</link></item>
      <item><title>Two</title><link>https://example.gov/two</link></item>
    </channel></rss>"""
    assert feed_urls(xml) == ["https://example.gov/one", "https://example.gov/two"]


def test_atom_links_are_parsed() -> None:
    xml = """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><link href="https://example.gov/atom-one"/></entry>
    </feed>"""
    assert feed_urls(xml) == ["https://example.gov/atom-one"]


def test_broken_xml_is_not_a_crash() -> None:
    assert sitemap_urls("<urlset><url>") == []
    assert feed_urls("not xml at all") == []


# -- discovery during a crawl ----------------------------------------------


def test_pages_from_the_sitemap_are_read(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    urls = {page.final_url for page in result.pages}
    assert f"{base_url}/scholarships/from-sitemap.html" in urls


def test_the_sitemap_index_is_followed(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    assert "/sitemap-child.xml" in requested_paths()
    assert f"{base_url}/scholarships/from-sitemap.html" in {
        page.final_url for page in result.pages
    }


def test_pages_from_the_feed_are_read(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    assert f"{base_url}/scholarships/from-feed.html" in {
        page.final_url for page in result.pages
    }


def test_same_site_links_are_followed(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    assert f"{base_url}/scholarships/apply.html" in {
        page.final_url for page in result.pages
    }


def test_depth_zero_reads_only_the_start_page(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url, depth=0))
    urls = {page.final_url for page in result.pages}
    assert f"{base_url}/scholarships/index.html" in urls
    assert f"{base_url}/scholarships/apply.html" not in urls


def test_pages_outside_the_allowed_paths_are_never_fetched(base_url: str) -> None:
    make_crawler(max_pages=20).crawl(make_source(base_url))
    assert "/private/never.html" not in requested_paths()


def test_off_site_links_are_never_followed(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    assert all("example.com" not in page.url for page in result.pages)


def test_robots_txt_is_obeyed(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    assert "/scholarships/blocked/secret.html" not in requested_paths()
    assert any("robots.txt" in note for note in result.skipped)


def test_a_pdf_on_the_portal_is_read_through_its_text_layer(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    pdf_pages = [page for page in result.pages if page.kind == "pdf"]
    assert [page.url for page in pdf_pages] == [f"{base_url}/scholarships/file.pdf"]
    page = pdf_pages[0]
    assert "Deadline: 5 November 2026" in page.text
    assert any("PDF" in warning for warning in page.warnings)
    assert page.sha256 == hashlib.sha256(BROCHURE_PDF).hexdigest()


def test_non_html_targets_are_reported_as_errors(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    assert "/scholarships/poster" not in {page.url for page in result.pages}
    assert any("poster" in problem for problem in result.errors)


def test_a_redirect_is_followed_and_the_final_url_is_recorded(base_url: str) -> None:
    result = make_crawler(max_pages=20).crawl(make_source(base_url))
    redirects = [
        page for page in result.pages
        if page.url == f"{base_url}/scholarships/redirect-scholarship"
    ]
    assert redirects, "the redirecting link should be read"
    assert redirects[0].final_url == f"{base_url}/scholarships/apply.html"


# -- conditional requests ---------------------------------------------------


def test_a_second_visit_sends_the_etag_and_reports_unchanged(base_url: str) -> None:
    source = Source(
        name="Test Portal",
        base_url=f"{base_url}/scholarships/etag-scholarship.html",
        country="Testland",
        trust_level="official",
        allowed_path_prefixes=("/scholarships/etag-scholarship.html",),
        crawl_depth=0,
    )
    first = make_crawler(max_pages=5)
    first_result = first.crawl(source)
    assert [page.url for page in first_result.pages] == [source.base_url]
    assert first.conditional[source.base_url][0] == '"v1"'

    REQUESTS.clear()
    second = make_crawler(max_pages=5, conditional=first.conditional)
    second_result = second.crawl(source)
    assert second_result.pages == []
    assert second_result.unchanged == [source.base_url]
    sent = [headers for path, headers in REQUESTS if path == "/scholarships/etag-scholarship.html"]
    assert sent and sent[0].get("if-none-match") == '"v1"'


# -- pacing -----------------------------------------------------------------


def test_the_default_pace_is_one_request_per_second() -> None:
    assert MIN_INTERVAL_SECONDS == 1.0


def test_the_throttle_waits_between_two_requests_to_one_host() -> None:
    clock = {"now": 0.0}
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["now"] += seconds

    throttle = HostThrottle(
        min_interval=1.0, sleep=fake_sleep, clock=lambda: clock["now"]
    )
    throttle.wait("example.gov")
    assert slept == []  # the first request never waits
    clock["now"] += 0.25
    throttle.wait("example.gov")
    assert slept == [pytest.approx(0.75)]


def test_the_throttle_treats_each_host_separately() -> None:
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    throttle = HostThrottle(min_interval=1.0, sleep=fake_sleep, clock=lambda: 0.0)
    throttle.wait("one.gov")
    throttle.wait("two.gov")
    assert slept == []


def test_a_crawl_delay_can_only_slow_a_host_down() -> None:
    throttle = HostThrottle(min_interval=1.0, sleep=lambda _s: None)
    throttle.set_delay("slow.gov", 5.0)
    throttle.set_delay("fast.gov", 0.1)
    assert throttle.interval_for("slow.gov") == 5.0
    assert throttle.interval_for("fast.gov") == 1.0


# -- limits and safety ------------------------------------------------------


def test_the_page_cap_ends_the_run(base_url: str) -> None:
    result = make_crawler(max_pages=2).crawl(make_source(base_url))
    assert len(result.pages) == 2
    assert any("limit" in note for note in result.skipped)


def test_a_private_address_is_refused_without_connecting() -> None:
    source = Source(
        name="Metadata",
        base_url="http://169.254.169.254/latest/meta-data/",
        country="Nowhere",
        trust_level="official",
        allowed_path_prefixes=("/latest/meta-data/",),
        crawl_depth=1,
    )
    result = Crawler(allow_loopback=False).crawl(source)
    assert result.pages == []
    assert result.errors and "cannot be read safely" in result.errors[0]


def test_a_disabled_source_is_skipped_without_a_request() -> None:
    source = Source(
        name="Off",
        base_url="http://127.0.0.1:9/scholarships/",
        country="Testland",
        trust_level="official",
        allowed_path_prefixes=("/scholarships/",),
        crawl_depth=1,
        enabled=False,
    )
    result = make_crawler().crawl(source)
    assert result.pages == []
    assert result.skipped


def test_paths_match_regardless_of_case() -> None:
    source = make_source("https://example.gov")
    assert source.allows_path("/SCHOLARSHIPS/apply.html") is True
