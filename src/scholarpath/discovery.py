"""Finding candidate scholarship pages on an official site (G134).

This is **discovery, not verification**. The app still has no web-search API,
so it cannot go looking for scholarships on its own. What it can do honestly:
take one page the student trusts (a university's scholarships page, a
government funding portal, a listing page) and read the links that page itself
publishes, keeping only the ones that look like scholarship/funding pages on
the same site.

Nothing is invented: every candidate URL comes from an `href` printed on the
page that was fetched, and every candidate is then verified through the
existing pipeline (fetch -> model proposes fields -> verbatim check -> the
student confirms). Links are untrusted web content and are treated as data.

Rules kept deliberately strict:
- http(s) only, same site only (the page's own domain or its subdomains);
- documents (PDF, DOCX, ...) are skipped because the reading pipeline only
  accepts web pages;
- duplicates are dropped, and the list is capped so a big site cannot flood
  the screen;
- the page's own anchors, mail/telephone links and scripts are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit

from scholarpath.sources import fetch_html

MAX_CANDIDATES = 12

# Words that make a link look like a scholarship/funding page. Matched against
# the link text and the URL path, case-insensitively.
KEYWORDS = (
    "scholarship",
    "scholarships",
    "scholar",
    "funding",
    "fund",
    "grant",
    "bursary",
    "fellowship",
    "studentship",
    "financial aid",
    "financial support",
    "award",
    "stipend",
    "tuition",
    "fee waiver",
)

_SKIP_TARGETS = (
    "mailto:",
    "tel:",
    "javascript:",
    "data:",
)
_SKIP_SUFFIXES = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".mp4", ".mp3", ".webp", ".ico",
)


@dataclass(frozen=True)
class Candidate:
    """One link found on the fetched page that may be a scholarship page."""

    url: str
    label: str
    source_url: str


@dataclass(frozen=True)
class Discovery:
    """The result of looking for candidates on one page."""

    source_url: str
    final_url: str
    title: str
    candidates: tuple[Candidate, ...]

    @property
    def empty(self) -> bool:
        return not self.candidates


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.title = ""
        self._href: str | None = None
        self._text: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - stdlib API
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "a":
            href = dict(attrs).get("href")
            if href and href.strip():
                self._href = href.strip()
                self._text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


class _FeedParser(HTMLParser):
    """Reads <link rel="alternate" type="application/rss+xml"> declarations."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.feeds: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - stdlib API
        if tag.lower() != "link":
            return
        data = {key.lower(): (value or "") for key, value in attrs}
        rel = data.get("rel", "").lower()
        media = data.get("type", "").lower()
        if "alternate" in rel and ("rss" in media or "atom" in media):
            href = data.get("href", "").strip()
            if href:
                self.feeds.append(href)


def _site_key(host: str) -> str:
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _same_site(candidate_host: str, page_host: str) -> bool:
    """True for the page's own host or one of its subdomains."""
    left, right = _site_key(candidate_host), _site_key(page_host)
    return left == right or left.endswith("." + right) or right.endswith("." + left)


def _looks_like_scholarship(text: str) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in KEYWORDS)


def _fallback_label(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    tail = path.rsplit("/", 1)[-1] if path else ""
    tail = re.sub(r"\.(html?|php|aspx?)$", "", tail, flags=re.IGNORECASE)
    words = re.sub(r"[-_]+", " ", tail).strip()
    return words.title() if words else "Open page"


def page_links(html: str, page_url: str) -> list[tuple[str, str]]:
    """Every usable link on a page: (absolute URL, link text), in page order.

    Documents, anchors, mail/telephone links and off-site links are dropped.
    The crawler uses this to follow a site's own navigation; the discovery
    flow below narrows the same links down to scholarship pages.
    """
    parser = _LinkParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - broken HTML must not crash discovery
        pass

    page_host = urlsplit(page_url).netloc
    seen: set[str] = set()
    links: list[tuple[str, str]] = []
    for href, label in parser.links:
        target = href.strip()
        if not target or target.startswith("#") or target.startswith(_SKIP_TARGETS):
            continue
        absolute = urldefrag(urljoin(page_url, target))[0]
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            continue
        if not _same_site(parts.netloc, page_host):
            continue
        if parts.path.casefold().endswith(_SKIP_SUFFIXES):
            continue
        key = absolute.casefold().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        links.append((absolute, label))
    return links


def alternate_feeds(html: str, page_url: str) -> list[str]:
    """Feed URLs the page itself advertises (<link rel="alternate">)."""
    parser = _FeedParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - broken HTML must not crash discovery
        pass
    feeds: list[str] = []
    seen: set[str] = set()
    for href in parser.feeds:
        absolute = urldefrag(urljoin(page_url, href))[0]
        if urlsplit(absolute).scheme not in ("http", "https"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        feeds.append(absolute)
    return feeds


def candidate_links(
    html: str, page_url: str, *, limit: int = MAX_CANDIDATES, same_site: bool = True
) -> list[Candidate]:
    """Scholarship-looking links published on one page, in page order."""
    parser = _LinkParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - broken HTML must not crash discovery
        pass

    page_host = urlsplit(page_url).netloc
    seen: set[str] = set()
    found: list[tuple[int, Candidate]] = []
    for href, label in parser.links:
        target = href.strip()
        if not target or target.startswith("#") or target.startswith(_SKIP_TARGETS):
            continue
        absolute = urljoin(page_url, target)
        absolute = urldefrag(absolute)[0]
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            continue
        if same_site and not _same_site(parts.netloc, page_host):
            continue
        lowered_path = parts.path.casefold()
        if lowered_path.endswith(_SKIP_SUFFIXES):
            continue
        if absolute.casefold() == urldefrag(page_url)[0].casefold():
            continue
        haystack = f"{parts.path} {label}"
        if not _looks_like_scholarship(haystack):
            continue
        key = absolute.casefold().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        # A keyword in the visible link text is a stronger signal than one
        # hiding in the URL, so those come first; page order breaks ties.
        rank = 0 if _looks_like_scholarship(label) else 1
        found.append(
            (
                rank,
                Candidate(
                    url=absolute,
                    label=label or _fallback_label(absolute),
                    source_url=page_url,
                ),
            )
        )
        if len(found) >= limit:
            break

    found.sort(key=lambda item: item[0])
    return [candidate for _rank, candidate in found[:limit]]


def discover(
    page_url: str, *, limit: int = MAX_CANDIDATES, timeout: float = 15.0
) -> Discovery:
    """Fetch one page and list the scholarship links it publishes.

    Raises `sources.FetchError` with a student-facing reason when the page
    cannot be read.
    """
    html, final_url = fetch_html(page_url, timeout=timeout)
    parser = _LinkParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - broken HTML must not crash discovery
        pass
    candidates = candidate_links(html, final_url, limit=limit)
    return Discovery(
        source_url=page_url,
        final_url=final_url,
        title=parser.title.strip(),
        candidates=tuple(candidates),
    )
