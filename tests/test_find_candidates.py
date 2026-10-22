"""The dev-side candidate finder (G189): filters, caps, file, no network.

The tool is loaded straight from `tools/find_candidates.py` (it is not part of
the app package), and every index answer is injected - the suite never touches
the real Common Crawl index.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "scholarpath_find_candidates", ROOT / "tools" / "find_candidates.py"
)
assert _spec is not None and _spec.loader is not None
find_candidates = importlib.util.module_from_spec(_spec)
# dataclasses resolves annotations through sys.modules, so register first.
sys.modules[_spec.name] = find_candidates
_spec.loader.exec_module(find_candidates)

ENDPOINT = "https://index.example.invalid/CC-MAIN-2026-43-index"
COLLECTION = "CC-MAIN-2026-43"
GOOD = "https://www.studyinkorea.go.kr/scholarship/2027"
BEST = "https://www.studyinkorea.go.kr/scholarship/apply-now"
PDF = "https://www.gks.go.kr/scholarship/brochure.pdf"


def _row(url: str, status: str = "200", mime: str = "text/html") -> dict:
    return {"url": url, "status": status, "mime": mime}


def _payload(*rows: dict) -> str:
    return "\n".join(json.dumps(row) for row in rows) + "\n"


def _no_sleep(_seconds: float) -> None:
    return None


def _run(tmp_path: Path, payloads: list[str], **kwargs):
    """Run the tool against canned index answers, in order."""
    queued = list(payloads)
    calls: list[str] = []

    def fetcher(url: str) -> str:
        calls.append(url)
        if not queued:
            return ""
        return queued.pop(0)

    kwargs.setdefault("suffixes", ["go.kr"])
    kwargs.setdefault("keywords", ["scholarship"])
    kwargs.setdefault("out", tmp_path / "review.txt")
    stats = find_candidates.run(
        kwargs.pop("suffixes"),
        kwargs.pop("keywords"),
        collection=COLLECTION,
        endpoint=ENDPOINT,
        fetcher=fetcher,
        sleeper=_no_sleep,
        now=datetime(2026, 10, 22, 15, 0, 0),
        **kwargs,
    )
    return stats, calls


# -- the suffix rule --------------------------------------------------------


def test_a_suffix_matches_the_registrable_way() -> None:
    assert find_candidates.matches_suffix("www.studyinkorea.go.kr", ("go.kr",))
    assert find_candidates.matches_suffix("go.kr", ("go.kr",))
    assert find_candidates.matches_suffix("school.ac.kr", ("go.kr", "ac.kr"))
    assert not find_candidates.matches_suffix("go.kr.fake.com", ("go.kr",))
    assert not find_candidates.matches_suffix("fakego.kr", ("go.kr",))
    assert not find_candidates.matches_suffix("", ("go.kr",))


# -- what is worth a human look ---------------------------------------------


def test_only_official_html_or_pdf_candidates_are_kept() -> None:
    payload = (
        _payload(
            _row(GOOD),
            _row(PDF, mime="application/pdf"),
            _row("https://www.studyinkorea.go.kr/scholarship/login"),
            _row("https://www.studyinkorea.go.kr/scholarship/gone", status="404"),
            _row("https://www.studyinkorea.go.kr/scholarship/poster.png", mime="image/png"),
            _row("https://scholarship.go.kr.fake.com/scholarship/x"),
            _row("https://www.studyinkorea.go.kr/about-us"),
        )
        + '{"blockDescription": "huge result set", "blocks": 3}\n'
    )
    candidates = find_candidates.select_candidates(payload, ("go.kr",))
    assert [candidate.url for candidate in candidates] == [PDF, GOOD]
    assert all(candidate.status == "200" for candidate in candidates)
    assert candidates[0].mime == "application/pdf"


def test_candidates_are_ordered_by_the_scholarship_score() -> None:
    candidates = find_candidates.select_candidates(
        _payload(_row(GOOD), _row(BEST)), ("go.kr",)
    )
    assert candidates[0].url == BEST
    assert candidates[0].score > candidates[1].score


def test_duplicates_collapse() -> None:
    candidates = find_candidates.select_candidates(
        _payload(_row(GOOD), _row(GOOD + "/")), ("go.kr",)
    )
    assert len(candidates) == 1


def test_tracking_parameters_are_dropped() -> None:
    candidates = find_candidates.select_candidates(
        _payload(
            _row("https://www.chevening.org/scholarships/who-can-apply/?utm_source=mail"),
            _row("https://www.chevening.org/scholarships/who-can-apply/?fbclid=abc"),
        ),
        ("chevening.org",),
    )
    assert [candidate.url for candidate in candidates] == [
        "https://www.chevening.org/scholarships/who-can-apply/"
    ]


# -- the review file --------------------------------------------------------


def test_the_review_file_is_written_and_says_what_it_is(tmp_path: Path) -> None:
    stats, calls = _run(tmp_path, [_payload(_row(GOOD))])
    assert len(calls) == 1
    assert "url=*.go.kr/scholarship*" in calls[0]

    text = Path(stats.path).read_text(encoding="utf-8")
    assert text.startswith("# ScholarPath candidate list")
    assert "FOR REVIEW ONLY" in text
    assert "# generated: 2026-10-22T15:00:00" in text
    assert COLLECTION in text
    assert "# targets: go.kr" in text
    assert "# keywords: scholarship" in text
    assert "Nothing here is verified" in text
    assert GOOD in text
    assert stats.kept == 1 and stats.rows == 1


def test_the_review_file_is_written_even_when_nothing_is_found(tmp_path: Path) -> None:
    stats, _calls = _run(tmp_path, [""])
    text = Path(stats.path).read_text(encoding="utf-8")
    assert "# candidates: 0" in text
    assert stats.kept == 0


# -- caps, failures, pacing -------------------------------------------------


def test_the_query_cap_is_kept(tmp_path: Path) -> None:
    stats, calls = _run(
        tmp_path,
        [_payload(_row(GOOD)), _payload(_row(GOOD))],
        keywords=["scholarship", "fellowship", "funding"],
        max_queries=2,
    )
    assert len(calls) == 2
    assert stats.queries == 2
    assert any("query cap" in error for error in stats.errors)


def test_the_candidate_cap_is_kept(tmp_path: Path) -> None:
    rows = [
        _row(f"https://www.studyinkorea.go.kr/scholarship/{index}")
        for index in range(20)
    ]
    stats, _calls = _run(tmp_path, [_payload(*rows)], max_candidates=5)
    assert stats.kept == 5
    lines = Path(stats.path).read_text(encoding="utf-8").splitlines()
    assert len([line for line in lines if not line.startswith("#")]) == 5


def test_a_failed_query_is_reported_not_raised(tmp_path: Path) -> None:
    def fetcher(_url: str) -> str:
        raise OSError("the index is busy")

    stats = find_candidates.run(
        ["go.kr"],
        ["scholarship"],
        out=tmp_path / "review.txt",
        collection=COLLECTION,
        endpoint=ENDPOINT,
        fetcher=fetcher,
        sleeper=_no_sleep,
    )
    assert stats.failed == 1
    assert stats.queries == 1
    assert any("the index is busy" in error for error in stats.errors)
    assert Path(stats.path).exists()


def test_requests_are_paced_one_second_apart(tmp_path: Path) -> None:
    slept: list[float] = []
    calls: list[str] = []

    def fetcher(url: str) -> str:
        calls.append(url)
        return _payload(_row(GOOD))

    stats = find_candidates.run(
        ["go.kr"],
        ["scholarship"],
        out=tmp_path / "review.txt",
        collection=COLLECTION,
        endpoint=ENDPOINT,
        pages=2,
        fetcher=fetcher,
        sleeper=slept.append,
    )
    assert len(calls) == 2
    assert slept == [1.0]
    assert stats.queries == 2


# -- how a target is asked for ------------------------------------------------


def test_a_host_is_asked_with_a_prefix_query() -> None:
    url = find_candidates.query_url(ENDPOINT, "www.studyinkorea.go.kr", "scholarship")
    assert "url=www.studyinkorea.go.kr/scholarship*" in url
    assert "*.go.kr" not in url


def test_a_suffix_is_asked_with_a_wildcard_host() -> None:
    url = find_candidates.query_url(ENDPOINT, "go.kr", "scholarship")
    assert "url=*.go.kr/scholarship*" in url


def test_a_host_and_a_suffix_are_told_apart() -> None:
    assert find_candidates.is_host("www.studyinkorea.go.kr") is True
    assert find_candidates.is_host("go.kr") is False


# -- the index being busy ----------------------------------------------------


def test_the_index_being_busy_is_retried(tmp_path: Path) -> None:
    attempts = {"count": 0}
    paused: list[float] = []

    def fetcher(_url: str) -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise find_candidates.IndexBusy("HTTP 504")
        return _payload(_row(GOOD))

    stats = find_candidates.run(
        ["go.kr"],
        ["scholarship"],
        out=tmp_path / "review.txt",
        collection=COLLECTION,
        endpoint=ENDPOINT,
        fetcher=fetcher,
        sleeper=paused.append,
    )
    assert attempts["count"] == 3
    assert stats.answered == 1
    assert stats.failed == 0
    assert stats.kept == 1
    assert paused  # it waited before trying again


def test_a_query_that_never_answers_is_reported_as_unknown(tmp_path: Path) -> None:
    def fetcher(_url: str) -> str:
        raise find_candidates.IndexBusy("HTTP 504")

    stats = find_candidates.run(
        ["go.kr"],
        ["scholarship"],
        out=tmp_path / "review.txt",
        collection=COLLECTION,
        endpoint=ENDPOINT,
        fetcher=fetcher,
        sleeper=_no_sleep,
        retries=1,
    )
    assert stats.failed == 1
    assert stats.busy == 1
    assert stats.complete is False
    assert any("nothing is known here" in error for error in stats.errors)
    text = Path(stats.path).read_text(encoding="utf-8")
    assert "# INCOMPLETE" in text


# -- the registry is the cheap source of targets ----------------------------


def test_the_registry_hosts_are_official_hosts() -> None:
    hosts = find_candidates.registry_hosts()
    assert hosts, "the shipped registry lists official portals"
    assert all("." in host for host in hosts)
    assert len(hosts) == len(set(hosts))


# -- not shipped in the app -------------------------------------------------

def test_the_tool_is_not_bundled_in_the_app() -> None:
    spec = (ROOT / "packaging" / "scholarpath.spec").read_text(encoding="utf-8")
    assert "find_candidates" not in spec
    assert "tools/" not in spec


def test_no_app_module_reads_the_candidate_finder() -> None:
    for path in (ROOT / "src" / "scholarpath").rglob("*.py"):
        assert "find_candidates" not in path.read_text(encoding="utf-8"), path
