"""Find candidate scholarship pages in the Common Crawl URL index (G189).

**Developer tool. It is not part of the app.** `packaging/scholarpath.spec`
bundles only `src/scholarpath`, no application module imports this file, and
nothing in the app reads the review file it writes.

What it does:

1. asks the Common Crawl **URL index** for addresses under the official sites
   the developer names - a host (`www.studyinkorea.go.kr`) or a suffix
   (`go.kr`, `ac.kr`, `gov.np`, ...) - whose path starts with a scholarship
   keyword;
2. keeps only http(s) rows on those sites, inside a resolution the official
   rule accepts (the host *is* the target or ends with `.target`), that the
   site served with a 2xx status as HTML or PDF;
3. drops obvious non-content (login, cart, archive, calendar...) with the same
   rule the crawler uses, and drops anything that says nothing about money
   for study;
4. orders what is left by the same scholarship score the crawler uses, and
   writes a review file with one candidate per line.

What it never does: fetch a candidate page, write to the catalog database,
download Common Crawl's crawled page content (only URL metadata is read), or
pretend a candidate is verified. Each address in the review file still has to
be fetched **live from its official site** and pass the word-for-word
pipeline before anything is stored.

What the index is like in practice (checked live on 2026-10-22):

- a **host** query is a prefix lookup and answers quickly;
- a **suffix** query asks the index for a whole country domain. It often
  answers with a timeout (HTTP 504) or with an arbitrary slice of the domain,
  and it does not really filter on the path. A suffix run is therefore a best
  effort and is reported as such;
- the index is busy at times and answers 504/503/429. Those are retried a few
  times, and a query that never answered is reported as **unknown**, not as
  "nothing there".

Politeness: one index request per second, a cap on queries per run, a cap on
candidates collected, and a failed query is reported instead of ending the run.

Usage::

    python tools/find_candidates.py www.studyinkorea.go.kr www.gks.go.kr
    python tools/find_candidates.py go.kr --keyword scholarship --keyword janghak
    python tools/find_candidates.py www.studyinkorea.go.kr --prefix scholarship
    python tools/find_candidates.py --list-collections
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from scholarpath.discovery import is_noise, score_link  # noqa: E402 - path set above

COLLECTIONS_URL = "https://index.commoncrawl.org/collinfo.json"
USER_AGENT = (
    "ScholarPath-candidates/0.1 (developer tool; official pages are fetched "
    "and verified separately)"
)

#: At most one request per second to the shared index, as Common Crawl asks.
MIN_INTERVAL_SECONDS = 1.0
TIMEOUT = 30.0
MAX_RESPONSE_BYTES = 4_000_000
PAGE_SIZE = 100
MAX_QUERIES = 12
MAX_CANDIDATES = 200
RETRIES = 2
RETRY_PAUSE = 2.0

DEFAULT_KEYWORDS = (
    "scholarship",
    "fellowship",
    "bursary",
    "grant",
    "funding",
    "stipendium",
    "bourse",
    "beca",
    "bolsa",
    "beasiswa",
    "janghak",
    "chhatrabritti",
)

DEFAULT_SUFFIXES = ("go.kr", "ac.kr")

_KEPT_TYPES = ("text/html", "application/xhtml+xml", "application/pdf")


class IndexUnavailable(RuntimeError):
    """The index could not be asked (bad collection, no network, bad answer)."""


class IndexBusy(RuntimeError):
    """The index is busy right now (it answers 504/503/429 under load)."""


#: The answers that mean "try again later", not "no such page".
BUSY_STATUS = (429, 500, 502, 503, 504)


@dataclass(frozen=True)
class Candidate:
    """One address from the index that looks like a scholarship page."""

    url: str
    host: str
    score: int
    status: str
    mime: str


@dataclass
class RunStats:
    """What the run actually did - nothing here is a verification."""

    collection: str = ""
    queries: int = 0
    answered: int = 0
    failed: int = 0
    busy: int = 0
    rows: int = 0
    kept: int = 0
    path: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """True when every query that was asked actually answered."""
        return self.failed == 0

    def summary(self) -> str:
        parts = [
            f"{self.queries} query(ies)",
            f"{self.rows} row(s) seen",
            f"{self.kept} candidate(s)",
        ]
        if self.failed:
            parts.append(f"{self.failed} query(ies) did not answer")
        return ", ".join(parts)


# -- talking to the index ---------------------------------------------------


def fetch_text(url: str, timeout: float = TIMEOUT) -> str:
    """Read one index response. The only network call this tool makes."""
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES)
    except HTTPError as exc:
        if exc.code == 404:
            # The index answers "nothing under this prefix" with a 404.
            return ""
        if exc.code in BUSY_STATUS:
            raise IndexBusy(f"HTTP {exc.code}") from exc
        raise IndexUnavailable(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise IndexUnavailable(f"the index could not be reached: {exc.reason}") from exc
    return body.decode("utf-8", errors="replace")


def collections(fetcher=fetch_text) -> list[dict[str, str]]:
    """The index collections Common Crawl publishes, newest first."""
    try:
        data = json.loads(fetcher(COLLECTIONS_URL))
    except Exception as exc:  # noqa: BLE001 - the caller reports a plain reason
        raise IndexUnavailable(f"the collection list could not be read: {exc}") from exc
    if not isinstance(data, list):
        raise IndexUnavailable("the collection list was not a list of collections.")
    return [entry for entry in data if isinstance(entry, dict) and entry.get("cdx-api")]


def index_endpoint(collection: str = "", *, fetcher=fetch_text) -> tuple[str, str]:
    """(endpoint, collection id). An empty collection means "the newest one"."""
    published = collections(fetcher=fetcher)
    if not published:
        raise IndexUnavailable("Common Crawl published no index collection.")
    if not collection:
        newest = published[0]
        return str(newest["cdx-api"]), str(newest.get("id", ""))
    for entry in published:
        if entry.get("id") == collection:
            return str(entry["cdx-api"]), str(entry["id"])
    known = ", ".join(str(entry.get("id")) for entry in published[:5])
    raise IndexUnavailable(f"unknown collection {collection!r}; newest are: {known}")


def is_host(target: str) -> bool:
    """Is this a specific host (`www.studyinkorea.go.kr`) rather than a suffix?

    A suffix (`go.kr`) has two labels; a host has three or more. Hosts give
    the index a precise prefix to look up; a suffix asks it for everything
    under a country domain, which is a scan it often refuses.
    """
    labels = [label for label in (target or "").strip().lower().split(".") if label]
    return len(labels) >= 3


def query_url(
    endpoint: str,
    target: str,
    pattern: str,
    *,
    page: int = 0,
    limit: int = PAGE_SIZE,
) -> str:
    """One URL-index query for `target`, paths starting with `pattern`.

    - a **host** is asked with a prefix query (`www.example.go.kr/scholarship*`),
      which is the shape the index answers quickly;
    - a **suffix** is asked with a wildcard host (`*.go.kr/scholarship*`), and
      the index may answer slowly or refuse with a timeout, because it has to
      walk a whole country domain. Whatever comes back is filtered here, so a
      suffix query is a best effort, never a complete list.

    Wildcards are only honoured at the end of a URL match, so the pattern is a
    path *prefix*, never a fragment in the middle. The wildcards themselves
    are sent literally, the way Common Crawl's own examples show them.
    """
    if is_host(target):
        base = quote(target.strip().lower(), safe="*")
    else:
        base = f"*.{target.strip().lower()}"
    query = f"url={base}/{quote(pattern, safe='*')}*&output=json&collapse=urlkey"
    if limit:
        query += f"&limit={limit}"
    if page:
        query += f"&page={page}"
    return f"{endpoint}?{query}"


# -- filtering --------------------------------------------------------------


def matches_suffix(host: str, rules: tuple[str, ...] | list[str]) -> bool:
    """The official rule, registrable style: is the host *under* this target?

    A lookalike (`go.kr.example.com`, `fakego.kr`) never matches.
    """
    host = (host or "").lower().rstrip(".")
    if not host:
        return False
    return any(host == rule or host.endswith("." + rule) for rule in rules)


def rows(payload: str) -> list[dict]:
    """The JSON lines of an index answer, metadata lines skipped."""
    parsed: list[dict] = []
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("url"):
            parsed.append(row)
    return parsed


#: Parameters that only follow a person around; they are dropped so the same
#: page is not listed twice.
_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
    "ref",
}


def clean_url(url: str) -> str:
    """The address without tracking parameters."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not name.casefold().startswith("utm_")
        and name.casefold() not in _TRACKING_PARAMS
    ]
    if not kept:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def select_candidates(
    payload: str, rules: tuple[str, ...] | list[str]
) -> list[Candidate]:
    """The rows worth a human look, best score first, duplicates collapsed."""
    found: dict[str, Candidate] = {}
    for row in rows(payload):
        url = clean_url(str(row.get("url") or "").strip())
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            continue
        host = (parts.hostname or "").lower()
        if not matches_suffix(host, rules):
            continue
        if is_noise(url):
            continue
        status = str(row.get("status") or "")
        if not status.startswith("2"):
            continue
        mime = str(row.get("mime") or row.get("mime-detected") or "")
        mime = mime.split(";")[0].strip().lower()
        if mime and mime not in _KEPT_TYPES:
            continue
        score = score_link(url)
        if score <= 0:
            continue
        key = url.casefold().rstrip("/")
        candidate = Candidate(
            url=url, host=host, score=score, status=status, mime=mime or "unknown"
        )
        current = found.get(key)
        if current is None or candidate.score > current.score:
            found[key] = candidate
    return sorted(found.values(), key=lambda item: (-item.score, item.url))


# -- the run ----------------------------------------------------------------


def _ask(
    url: str,
    *,
    fetcher,
    sleeper,
    retries: int,
    pause: float,
) -> tuple[str | None, str]:
    """Ask the index once, retrying while it is busy.

    Returns (payload, problem). An empty problem means the index answered.
    """
    problem = ""
    for attempt in range(retries + 1):
        try:
            return fetcher(url), ""
        except IndexBusy as exc:
            problem = f"the index was busy ({exc})"
            if attempt < retries:
                sleeper(pause * (attempt + 1))
                continue
            return None, problem
        except Exception as exc:  # noqa: BLE001 - report, keep going
            return None, str(exc)
    return None, problem


def collect(
    targets: tuple[str, ...] | list[str],
    keywords: tuple[str, ...] | list[str],
    *,
    collection: str = "",
    endpoint: str = "",
    prefixes: tuple[str, ...] | list[str] = (),
    pages: int = 1,
    page_size: int = PAGE_SIZE,
    max_queries: int = MAX_QUERIES,
    max_candidates: int = MAX_CANDIDATES,
    retries: int = RETRIES,
    pause: float = RETRY_PAUSE,
    fetcher=fetch_text,
    sleeper=time.sleep,
) -> tuple[list[Candidate], RunStats]:
    """Ask the index and return (candidates, honest stats). Writes nothing."""
    stats = RunStats()
    if not endpoint:
        endpoint, stats.collection = index_endpoint(collection, fetcher=fetcher)
    else:
        stats.collection = collection

    rules = tuple(targets)
    patterns = tuple(prefixes) or tuple(keywords)
    candidates: dict[str, Candidate] = {}
    requested = 0
    budget_hit = False

    for target in rules:
        for pattern in patterns:
            for page in range(max(1, pages)):
                if requested >= max_queries:
                    stats.errors.append(
                        f"query cap reached ({max_queries}); later queries were "
                        "not asked, so this list is not complete."
                    )
                    budget_hit = True
                    break
                if requested:
                    sleeper(MIN_INTERVAL_SECONDS)
                requested += 1
                stats.queries += 1
                url = query_url(
                    endpoint, target, pattern, page=page, limit=page_size
                )
                payload, problem = _ask(
                    url,
                    fetcher=fetcher,
                    sleeper=sleeper,
                    retries=retries,
                    pause=pause,
                )
                if payload is None:
                    stats.failed += 1
                    if "busy" in problem:
                        stats.busy += 1
                    stats.errors.append(f"{url} - {problem}; nothing is known here.")
                    break
                stats.answered += 1
                seen = rows(payload)
                stats.rows += len(seen)
                for candidate in select_candidates(payload, rules):
                    key = candidate.url.casefold().rstrip("/")
                    current = candidates.get(key)
                    if current is None or candidate.score > current.score:
                        candidates[key] = candidate
            if budget_hit:
                break
        if budget_hit:
            break

    ordered = sorted(candidates.values(), key=lambda item: (-item.score, item.url))
    if max_candidates > 0:
        ordered = ordered[:max_candidates]
    stats.kept = len(ordered)
    return ordered, stats


def review_text(
    candidates: list[Candidate],
    *,
    targets: tuple[str, ...] | list[str],
    keywords: tuple[str, ...] | list[str],
    collection: str,
    generated: str,
    complete: bool = True,
) -> str:
    """The review file: what was asked, and what is *not* claimed."""
    lines = [
        "# ScholarPath candidate list - FOR REVIEW ONLY, not a catalog.",
        f"# generated: {generated}",
        f"# index collection: {collection or 'unknown'}",
        f"# targets: {', '.join(targets)}",
        f"# keywords: {', '.join(keywords)}",
        f"# candidates: {len(candidates)}",
    ]
    if not complete:
        lines.append(
            "# INCOMPLETE: some queries did not answer, so pages may be missing."
        )
    lines += [
        "#",
        "# Nothing here is verified, and the app never reads this file:",
        "# nothing is stored in the catalog from it. Fetch a candidate live",
        "# from its official site and let the word-for-word pipeline check it.",
        "#",
        "# score\thost\tstatus\tmime\turl",
    ]
    for candidate in candidates:
        lines.append(
            f"{candidate.score}\t{candidate.host}\t{candidate.status}\t"
            f"{candidate.mime}\t{candidate.url}"
        )
    return "\n".join(lines) + "\n"


def write_review(path: str | Path, text: str) -> Path:
    """Write the review file (and its folder), with plain newlines."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def run(
    targets: tuple[str, ...] | list[str],
    keywords: tuple[str, ...] | list[str],
    *,
    out: str | Path,
    collection: str = "",
    endpoint: str = "",
    prefixes: tuple[str, ...] | list[str] = (),
    pages: int = 1,
    page_size: int = PAGE_SIZE,
    max_queries: int = MAX_QUERIES,
    max_candidates: int = MAX_CANDIDATES,
    retries: int = RETRIES,
    pause: float = RETRY_PAUSE,
    fetcher=fetch_text,
    sleeper=time.sleep,
    now: datetime | None = None,
) -> RunStats:
    """Ask the index, write the review file, return what really happened."""
    candidates, stats = collect(
        targets,
        keywords,
        collection=collection,
        endpoint=endpoint,
        prefixes=prefixes,
        pages=pages,
        page_size=page_size,
        max_queries=max_queries,
        max_candidates=max_candidates,
        retries=retries,
        pause=pause,
        fetcher=fetcher,
        sleeper=sleeper,
    )
    generated = (now or datetime.now()).isoformat(timespec="seconds")
    text = review_text(
        candidates,
        targets=tuple(targets),
        keywords=tuple(keywords),
        collection=stats.collection,
        generated=generated,
        complete=stats.complete,
    )
    stats.path = str(write_review(out, text))
    return stats


# -- the command line -------------------------------------------------------


def default_out(targets: tuple[str, ...] | list[str], today: datetime | None = None) -> Path:
    """Where a review file goes when the developer does not say."""
    stamp = (today or datetime.now()).strftime("%Y-%m-%d")
    name = "-".join(target.replace(".", "_") for target in targets) or "all"
    return _REPO / "tools" / "candidates" / f"candidates-{name}-{stamp}.txt"


def registry_hosts(sources=None) -> list[str]:
    """The hosts of the official portals in the sources registry.

    A host query is the shape the index answers quickly, so searching the
    registry's own portals is the cheapest way to use this tool.
    """
    if sources is None:
        from scholarpath.registry import load_registry

        sources = load_registry()
    hosts: list[str] = []
    for source in sources:
        host = (urlsplit(source.site_root).hostname or "").lower()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find candidate scholarship pages in the Common Crawl URL index. "
            "The output is a review file, never a catalog: fetch every candidate "
            "live and verify it before it is stored."
        )
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help=(
            "official hosts or suffixes to search "
            f"(default: {', '.join(DEFAULT_SUFFIXES)})"
        ),
    )
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help="a scholarship word used as a path prefix (repeatable)",
    )
    parser.add_argument(
        "--prefix",
        action="append",
        dest="prefixes",
        help="extra path prefix to try instead of the keywords (repeatable)",
    )
    parser.add_argument(
        "--collection",
        default="",
        help="index collection id (default: the newest one Common Crawl publishes)",
    )
    parser.add_argument(
        "--registry",
        action="store_true",
        help=(
            "search the hosts of the official portals in the sources registry "
            "instead of the names on the command line"
        ),
    )
    parser.add_argument("--pages", type=int, default=1, help="index pages per query")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--max-queries", type=int, default=MAX_QUERIES)
    parser.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    parser.add_argument("--retries", type=int, default=RETRIES)
    parser.add_argument(
        "--out", default="", help="review file (default: tools/candidates/...)"
    )
    parser.add_argument(
        "--list-collections",
        action="store_true",
        help="print the newest index collections and exit (one live request)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_collections:
        for entry in collections()[:10]:
            print(f"{entry.get('id')}\t{entry.get('name', '')}")
        return 0

    targets = tuple(args.targets) or DEFAULT_SUFFIXES
    if args.registry:
        hosts = registry_hosts()
        if not hosts:
            print("The sources registry lists no portal.", file=sys.stderr)
            return 2
        targets = tuple(hosts)
    keywords = tuple(args.keywords) or DEFAULT_KEYWORDS
    out = args.out or default_out(targets)

    try:
        stats = run(
            targets,
            keywords,
            out=out,
            collection=args.collection,
            prefixes=tuple(args.prefixes or ()),
            pages=args.pages,
            page_size=args.page_size,
            max_queries=args.max_queries,
            max_candidates=args.max_candidates,
            retries=args.retries,
        )
    except IndexUnavailable as exc:
        print(f"Could not ask the index: {exc}", file=sys.stderr)
        return 2

    print(f"{stats.summary()} -> {stats.path}")
    for error in stats.errors:
        print(f"  ! {error}", file=sys.stderr)
    if not stats.complete:
        print(
            "  the list is INCOMPLETE: some queries did not answer.",
            file=sys.stderr,
        )
    print(
        "  nothing is verified: fetch each candidate live and let the "
        "word-for-word pipeline check it.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
