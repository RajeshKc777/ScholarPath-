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
- documents (DOCX, XLSX, archives, images) are skipped; a PDF link is handed
  only to the crawler, which can read a text layer, never to the page flow;
- duplicates are dropped, and the list is capped so a big site cannot flood
  the screen;
- the page's own anchors, mail/telephone links and scripts are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

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


#: How strongly a word points at a scholarship page. The crawler reads the
#: highest scores first, so this is what decides which pages of a portal are
#: read in the time one run allows. 3 = the page is about money for study;
#: 2 = likely; 1 = worth a look if there is room left.
SCHOLARSHIP_TERMS: tuple[tuple[str, int], ...] = (
    # English - the task's own list, plus close synonyms.
    ("scholarship", 3),
    ("fellowship", 3),
    ("bursary", 3),
    ("studentship", 3),
    ("financial aid", 3),
    ("fee waiver", 3),
    ("tuition waiver", 3),
    ("grant", 2),
    ("funding", 2),
    ("funded", 2),
    ("fund", 2),
    ("stipend", 2),
    ("award", 2),
    ("tuition", 2),
    ("apply", 1),
    ("application", 1),
    ("eligib", 1),
    ("deadline", 1),
    # Local-language words for the same thing, so a portal that names the
    # scheme in its own language is not missed. These are matched as plain
    # substrings (no word boundaries exist for them in the regex sense).
    ("chhatrabritti", 3),  # Nepali, romanised
    ("छात्रवृत्ति", 3),  # Nepali / Hindi
    ("장학", 3),  # Korean
    ("奨学金", 3),  # Japanese
    ("奖学金", 3),  # Chinese, simplified
    ("獎學金", 3),  # Chinese, traditional
    ("beasiswa", 3),  # Indonesian
    ("biasiswa", 3),  # Malay
    ("học bổng", 3),  # Vietnamese
    ("hoc bong", 3),
    ("ทุนการศึกษา", 3),  # Thai
    ("stipendium", 3),  # German / Swedish / Danish
    ("bourse", 3),  # French
    ("beca", 3),  # Spanish
    ("bolsa", 3),  # Portuguese / Spanish
    ("stypendium", 3),  # Polish
    ("стипендия", 3),  # Russian
    ("منحة", 3),  # Arabic
    ("apuraha", 3),  # Swahili
)

#: Path segments that never hold scholarship content. A link whose path has
#: one of these as a whole segment is not queued: a login form, a shopping
#: cart, a news archive, a calendar, a tag list.
NOISE_SEGMENTS = frozenset(
    {
        "login",
        "log-in",
        "logout",
        "signin",
        "sign-in",
        "signup",
        "register",
        "account",
        "cart",
        "basket",
        "checkout",
        "payment",
        "calendar",
        "archive",
        "archives",
        "tag",
        "tags",
        "author",
        "search",
        "wp-login",
        "print",
        "share",
    }
)


def _term_present(term: str, haystack: str) -> bool:
    """Is this term in the text, without matching the middle of a word?

    Short ASCII words ("beca", "grant") would otherwise fire inside unrelated
    words ("because", "granted"), so they must be a whole word, optionally
    plural. Longer and non-Latin terms are distinctive enough as substrings.
    """
    if len(term) >= 6 or not term.isascii():
        return term in haystack
    return re.search(rf"(?<![a-z]){re.escape(term)}s?(?![a-z])", haystack) is not None


def score_link(url: str, label: str = "") -> int:
    """How strongly a link looks like a scholarship page (0 = not at all).

    The path and the visible link text are both read, lower-cased, with the
    separators a URL uses turned into spaces so "financial-aid" still matches.
    Percent-encoded paths are decoded first, which is how local-language links
    usually appear.
    """
    path = unquote(urlsplit(url).path)
    haystack = re.sub(r"[-_+]+", " ", f"{path} {label}".casefold())
    return sum(weight for term, weight in SCHOLARSHIP_TERMS if _term_present(term, haystack))


def is_noise(url: str) -> bool:
    """True for a page that cannot hold scholarship content (login, cart...)."""
    path = unquote(urlsplit(url).path).casefold()
    return any(segment in NOISE_SEGMENTS for segment in path.split("/") if segment)


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


def page_links(
    html: str, page_url: str, *, allow_pdf: bool = False
) -> list[tuple[str, str]]:
    """Every usable link on a page: (absolute URL, link text), in page order.

    Documents, anchors, mail/telephone links and off-site links are dropped -
    except PDFs when the caller asks for them (`allow_pdf`). The crawler can
    read a PDF's text layer; the discovery flow below still only opens pages.
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
            if not (allow_pdf and parts.path.casefold().endswith(".pdf")):
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
