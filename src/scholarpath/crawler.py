"""Crawling the official portals listed in the sources registry.

The crawler answers one question honestly: **which pages on this official
portal talk about a scholarship?** It never invents a page, never follows a
link off the portal, and never reads a page outside the paths the registry
allows.

How it finds pages:

1. **robots.txt** is read first and obeyed. A path the site disallows is
   skipped and reported - never fetched "just to see".
2. **sitemap.xml** (and a sitemap index, one level deep) - the site's own
   list of pages.
3. **RSS / Atom feeds** the site publishes - the site's own list of new
   items.
4. **Same-site links** on the pages it reads, one level per ``crawl_depth``.

Rules it keeps:

- one request per second per host (a portal's own ``Crawl-delay`` can make
  that slower, never faster);
- **HTML only** - a PDF or an image is not a page the app can read;
- **conditional requests** - the ETag / Last-Modified of the last visit is
  sent back, and a page the server says has not changed is not re-read;
- a hard cap on pages per run, so a run always ends.

Index files (robots.txt, sitemaps, feeds) are read even when they sit outside
the allowed paths - they are the site's own table of contents, not content.
Every page whose *content* is read must be inside the allowed paths.
"""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from scholarpath.discovery import KEYWORDS, alternate_feeds, page_links
from scholarpath.registry import Source
from scholarpath.sources import (
    XML_TYPES,
    BlockedRequest,
    FetchError,
    Page,
    Resource,
    fetch_resource,
    page_from_resource,
)

logger = logging.getLogger("scholarpath.crawler")

#: The token the crawler identifies itself with in robots.txt.
USER_AGENT = "ScholarPath"

#: At most one request per second per host.
MIN_INTERVAL_SECONDS = 1.0

#: How many pages one source may contribute to a run.
MAX_PAGES_PER_SOURCE = 10

#: How many sitemap files an index may point at.
MAX_SITEMAP_FILES = 5

_HTML_TYPES = ("text/html", "application/xhtml+xml")
_SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")
_FEED_PATHS = ("/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml", "/atom.xml")


# -- robots.txt ------------------------------------------------------------


@dataclass(frozen=True)
class _Rule:
    pattern: str
    allow: bool
    regex: re.Pattern[str]

    @property
    def length(self) -> int:
        """Longest-match wins, so the longer pattern counts."""
        return len(self.pattern.replace("*", "").replace("$", ""))


class RobotsRules:
    """The rules of one robots.txt, for one user agent.

    A path is allowed unless a matching `Disallow` is longer than every
    matching `Allow` - the usual "longest match wins" reading.
    """

    def __init__(self, rules: list[_Rule] = (), crawl_delay: float = 0.0,
                 present: bool = True) -> None:
        self._rules = list(rules)
        self.crawl_delay = crawl_delay
        self.present = present

    @classmethod
    def parse(cls, text: str, user_agent: str = USER_AGENT) -> RobotsRules:
        groups: list[dict] = []
        current: dict | None = None

        def group_for(agent: str) -> dict:
            for group in groups:
                if agent in group["agents"]:
                    return group
            group = {"agents": [], "rules": [], "delay": 0.0}
            groups.append(group)
            return group

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field_name, _, value = line.partition(":")
            field_name = field_name.strip().lower()
            value = value.strip()
            if field_name == "user-agent":
                agent = value.lower()
                if current is None or current["rules"] or current["delay"]:
                    current = None
                if current is None:
                    current = group_for(agent)
                current["agents"].append(agent)
            elif field_name in ("disallow", "allow"):
                if current is None:
                    current = group_for("*")
                if field_name == "disallow" and not value:
                    # "Disallow:" with no value forbids nothing.
                    continue
                current["rules"].append((value, field_name == "allow"))
            elif field_name == "crawl-delay":
                if current is None:
                    current = group_for("*")
                try:
                    delay = float(value)
                except ValueError:
                    delay = 0.0
                current["delay"] = max(current["delay"], delay)

        token = user_agent.lower()
        chosen: list[tuple[str, bool]] = []
        chosen_delay = 0.0
        wildcard: list[tuple[str, bool]] = []
        wildcard_delay = 0.0
        for group in groups:
            agents = group["agents"]
            matched = any(
                agent == token
                or (agent and agent in token)
                or (agent and token in agent and len(agent) > 3)
                for agent in agents
            )
            if matched:
                chosen.extend(group["rules"])
                chosen_delay = max(chosen_delay, group["delay"])
            elif "*" in agents:
                wildcard.extend(group["rules"])
                wildcard_delay = max(wildcard_delay, group["delay"])

        if not chosen:
            chosen = wildcard
            chosen_delay = wildcard_delay
        return cls(
            rules=[_Rule(pattern, allow, _pattern_to_regex(pattern))
                   for pattern, allow in chosen if pattern],
            crawl_delay=chosen_delay,
        )

    def allows(self, path: str) -> bool:
        """Is this path allowed for us?"""
        if not self._rules:
            return True
        best: _Rule | None = None
        for rule in self._rules:
            if not rule.regex.search(path):
                continue
            if best is None or rule.length > best.length:
                best = rule
            elif rule.length == best.length and rule.allow and not best.allow:
                best = rule
        return True if best is None else best.allow


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """robots.txt patterns: `*` matches anything, a trailing `$` is the end."""
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    escaped = "".join(
        ".*" if character == "*" else re.escape(character) for character in body
    )
    return re.compile("^" + escaped + ("$" if anchored_end else ""))


# -- pacing ----------------------------------------------------------------


class HostThrottle:
    """Keeps at least one second between two requests to the same host."""

    def __init__(
        self,
        min_interval: float = MIN_INTERVAL_SECONDS,
        sleep=time.sleep,
        clock=time.monotonic,
    ) -> None:
        self._min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._delays: dict[str, float] = {}

    def set_delay(self, host: str, delay: float) -> None:
        """A site's own Crawl-delay can slow this host down, never speed it up."""
        if delay > 0:
            self._delays[host] = delay

    def interval_for(self, host: str) -> float:
        return max(self._min_interval, self._delays.get(host, 0.0))

    def wait(self, host: str) -> float:
        """Block until this host may be asked again. Returns seconds slept."""
        interval = self.interval_for(host)
        now = self._clock()
        slept = 0.0
        last = self._last.get(host)
        if last is not None:
            remaining = interval - (now - last)
            if remaining > 0:
                self._sleep(remaining)
                slept = remaining
        self._last[host] = self._clock()
        return slept


# -- sitemaps and feeds ----------------------------------------------------


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def sitemap_urls(xml_text: str) -> list[str]:
    """The page URLs in a sitemap (a <urlset>)."""
    return _locations(xml_text, "url")


def sitemap_files(xml_text: str) -> list[str]:
    """The sitemap files in a sitemap index (a <sitemapindex>)."""
    return _locations(xml_text, "sitemap")


def _locations(xml_text: str, container: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    found: list[str] = []
    for element in root.iter():
        if _localname(element.tag) != container:
            continue
        for child in element:
            if _localname(child.tag) == "loc" and child.text:
                value = child.text.strip()
                if value and value not in found:
                    found.append(value)
    return found


def feed_urls(xml_text: str) -> list[str]:
    """The links in an RSS or Atom feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    found: list[str] = []
    for element in root.iter():
        name = _localname(element.tag)
        if name == "item":
            for child in element:
                if _localname(child.tag) == "link" and child.text:
                    value = child.text.strip()
                    if value and value not in found:
                        found.append(value)
        elif name == "entry":
            for child in element:
                if _localname(child.tag) != "link":
                    continue
                href = (child.attrib.get("href") or "").strip()
                if href and href not in found:
                    found.append(href)
    return found


# -- results ---------------------------------------------------------------


@dataclass(frozen=True)
class CrawlPage:
    """One page the crawler read, with its provenance."""

    url: str
    final_url: str
    title: str
    text: str
    sha256: str
    fetched_at: str
    etag: str = ""
    last_modified: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def domain(self) -> str:
        host = (urlsplit(self.final_url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host

    def to_page(self) -> Page:
        """The same page as a `sources.Page`, for the existing pipeline."""
        return Page(
            requested_url=self.url,
            final_url=self.final_url,
            title=self.title,
            text=self.text,
            fetched_at=self.fetched_at,
            sha256=self.sha256,
            truncated=False,
            warnings=list(self.warnings),
        )


@dataclass
class CrawlResult:
    """What one source contributed to a run."""

    source_name: str
    pages: list[CrawlPage] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


# -- the crawler ------------------------------------------------------------


class Crawler:
    """Reads the scholarship pages of one official portal.

    The crawler is deliberately boring: it obeys robots.txt, asks once per
    second, reads HTML only, and stops at the page cap.
    """

    def __init__(
        self,
        timeout: float = 20.0,
        max_pages: int = MAX_PAGES_PER_SOURCE,
        min_interval: float = MIN_INTERVAL_SECONDS,
        user_agent: str = USER_AGENT,
        allow_loopback: bool = False,
        conditional: dict[str, tuple[str, str]] | None = None,
        throttle: HostThrottle | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_pages = max_pages
        self.user_agent = user_agent
        self.allow_loopback = allow_loopback
        #: url -> (etag, last-modified) of the last successful read.
        self.conditional = dict(conditional or {})
        self.throttle = throttle or HostThrottle(min_interval)
        self._robots: dict[str, tuple[RobotsRules | None, str]] = {}

    # -- robots -----------------------------------------------------------
    def robots_for(self, url: str) -> tuple[RobotsRules | None, str]:
        """The rules of the host of this URL.

        Returns (rules, reason). The rules are None when the site's address
        itself may not be read - a private or metadata address is refused
        rather than crawled.
        """
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host:
            return None, "the address has no host name."
        if host in self._robots:
            return self._robots[host]
        rules, reason = self._load_robots(parts.scheme or "https", parts.netloc, host)
        self._robots[host] = (rules, reason)
        return rules, reason

    def _load_robots(
        self, scheme: str, netloc: str, host: str
    ) -> tuple[RobotsRules | None, str]:
        robots_url = f"{scheme}://{netloc}/robots.txt"
        try:
            resource = self._fetch(robots_url, XML_TYPES + ("text/plain",))
        except BlockedRequest as exc:
            logger.info("robots.txt of %s refused: %s", host, exc)
            return None, str(exc)
        except FetchError as exc:
            logger.info("robots.txt could not be read for %s: %s", host, exc)
            # No readable robots.txt means no rules are known: the crawl may
            # continue, and the reason is logged.
            return RobotsRules(rules=[], crawl_delay=0.0, present=False), ""
        rules = RobotsRules.parse(resource.text(), self.user_agent)
        if rules.crawl_delay:
            self.throttle.set_delay(host, rules.crawl_delay)
        return rules, ""

    # -- fetching ---------------------------------------------------------
    def _fetch(
        self,
        url: str,
        allowed_types: tuple[str, ...] = _HTML_TYPES,
        conditional: bool = False,
    ) -> Resource:
        host = (urlsplit(url).hostname or "").lower()
        self.throttle.wait(host)
        etag = last_modified = None
        if conditional:
            etag, last_modified = self.conditional.get(url, ("", ""))
        return fetch_resource(
            url,
            timeout=self.timeout,
            allow_loopback=self.allow_loopback,
            allowed_types=allowed_types,
            etag=etag or None,
            last_modified=last_modified or None,
        )

    def _remember(self, url: str, resource: Resource) -> None:
        if resource.etag or resource.last_modified:
            self.conditional[url] = (resource.etag, resource.last_modified)

    # -- discovery --------------------------------------------------------
    def sitemap_seeds(self, source: Source) -> list[str]:
        """Page URLs the site's own sitemap publishes, inside the allowed paths."""
        seeds: list[str] = []
        root = source.site_root
        for path in _SITEMAP_PATHS:
            try:
                resource = self._fetch(root + path, XML_TYPES)
            except FetchError as exc:
                logger.info("no sitemap at %s: %s", root + path, exc)
                continue
            text = resource.text()
            files = sitemap_files(text)
            for sitemap_file in files[:MAX_SITEMAP_FILES]:
                try:
                    nested = self._fetch(sitemap_file, XML_TYPES)
                except FetchError as exc:
                    logger.info("sitemap %s unreadable: %s", sitemap_file, exc)
                    continue
                for url in sitemap_urls(nested.text()):
                    if source.allows_url(url) and url not in seeds:
                        seeds.append(url)
            for url in sitemap_urls(text):
                if source.allows_url(url) and url not in seeds:
                    seeds.append(url)
            if seeds:
                break
        return seeds

    def feed_seeds(self, source: Source, extra_feeds: list[str] | None = None) -> list[str]:
        """Page URLs the site's own feeds publish, inside the allowed paths."""
        seeds: list[str] = []
        root = source.site_root
        candidates = [root + path for path in _FEED_PATHS]
        candidates.extend(extra_feeds or [])
        for feed_url in candidates:
            try:
                resource = self._fetch(feed_url, XML_TYPES)
            except FetchError as exc:
                logger.info("no feed at %s: %s", feed_url, exc)
                continue
            for url in feed_urls(resource.text()):
                if source.allows_url(url) and url not in seeds:
                    seeds.append(url)
            if seeds:
                break
        return seeds

    def link_seeds(self, source: Source, page_url: str, html: str) -> list[str]:
        """Same-site links on a page that look like scholarship pages."""
        seeds: list[str] = []
        for url, label in page_links(html, page_url):
            if not source.allows_url(url):
                continue
            path = urlsplit(url).path
            haystack = f"{path} {label}".casefold()
            if not any(keyword in haystack for keyword in KEYWORDS):
                continue
            if url not in seeds:
                seeds.append(url)
        return seeds

    # -- the run ----------------------------------------------------------
    def crawl(self, source: Source) -> CrawlResult:
        """Read the scholarship pages of one source."""
        result = CrawlResult(source_name=source.name)
        if not source.enabled:
            result.skipped.append(f"{source.name} is disabled in the registry.")
            return result

        rules, reason = self.robots_for(source.base_url)
        if rules is None:
            result.errors.append(
                f"{source.name}: the site's address cannot be read safely - {reason}"
            )
            return result

        queue: list[tuple[str, int]] = []
        seen: set[str] = set()

        def add(url: str, depth: int) -> None:
            if url in seen:
                return
            seen.add(url)
            queue.append((url, depth))

        for prefix in source.allowed_path_prefixes:
            add(urljoin(source.site_root, prefix), 0)
        if source.base_url not in seen:
            add(source.base_url, 0)

        for url in self.sitemap_seeds(source):
            add(url, 0)
        feed_urls_found = self.feed_seeds(source)
        for url in feed_urls_found:
            add(url, 0)

        depth = 0
        while queue and len(result.pages) < self.max_pages:
            url, depth = queue.pop(0)
            if not source.allows_url(url):
                result.skipped.append(f"{url} - outside the paths this portal allows.")
                continue
            if rules is not None and not rules.allows(urlsplit(url).path or "/"):
                result.skipped.append(f"{url} - robots.txt does not allow it.")
                continue
            try:
                resource = self._fetch(url, _HTML_TYPES, conditional=True)
            except FetchError as exc:
                result.errors.append(f"{url} - {exc}")
                continue

            if resource.not_modified:
                result.unchanged.append(url)
                continue

            self._remember(url, resource)
            try:
                page = page_from_resource(resource)
            except FetchError as exc:
                result.errors.append(f"{url} - {exc}")
                continue

            result.pages.append(
                CrawlPage(
                    url=url,
                    final_url=page.final_url,
                    title=page.title,
                    text=page.text,
                    sha256=page.sha256,
                    fetched_at=page.fetched_at,
                    etag=resource.etag,
                    last_modified=resource.last_modified,
                    warnings=tuple(page.warnings),
                )
            )

            if depth < source.crawl_depth:
                html = resource.text()
                for link in self.link_seeds(source, page.final_url, html):
                    add(link, depth + 1)
                for feed in alternate_feeds(html, page.final_url):
                    for item in self.feed_seeds(source, [feed]):
                        add(item, depth + 1)

        if queue:
            result.skipped.append(
                f"{len(queue)} page(s) were left out - the run reached its "
                f"limit of {self.max_pages} page(s) per portal."
            )
        return result
