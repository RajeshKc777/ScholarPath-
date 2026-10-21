"""The catalog run: crawl -> extract -> verify -> save, with no network.

A fake crawler supplies the pages and a fake gateway supplies the model's
proposals, so these tests exercise the real verification and storage code.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scholarpath.catalog import CatalogRunner, catalog_values
from scholarpath.crawler import CrawlPage, CrawlResult
from scholarpath.gateway.base import ChatResponse, ModelGateway
from scholarpath.registry import Source
from scholarpath.storage import Database, canonical_key, domain_of


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "catalog.db")
    yield database
    database.close()


PROVIDER = "Example Portal"

PAGE_TEXT = """OPEN GRANT 2026
Host country: Netherlands
Degree level: master's degrees
Fields of study: economics, public policy
Funding: fully funded tuition and a monthly allowance of EUR 1 200
Deadline: 5 November 2026
Language requirement: IELTS 6.5
Apply at https://example.gov/open-grant/apply
"""

PROPOSAL = {
    "title": "OPEN GRANT 2026",
    "host_country": "Netherlands",
    "degree_levels": "master's degrees",
    "disciplines": "economics, public policy",
    "funding_coverage": "fully funded tuition",
    "stipend": "EUR 1 200",
    "deadline": "5 November 2026",
    "language_requirement": "IELTS 6.5",
    "application_url": "https://example.gov/open-grant/apply",
}


def _reply(fields: dict[str, str | None]) -> str:
    return "```json\n" + json.dumps({"fields": fields}) + "\n```"


class _FakeGateway(ModelGateway):
    name = "fake"

    def __init__(self, replies: list[str] | str) -> None:
        self._replies = [replies] if isinstance(replies, str) else list(replies)
        self.prompts: list[str] = []

    def complete(self, request):  # type: ignore[override]
        self.prompts.append(request.messages[-1].content)
        reply = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        return ChatResponse(
            text=reply,
            model=request.model or "test-model",
            usage={"input": 1, "output": 1},
            finish_reason="stop",
        )


class _FakeCrawler:
    """Hands the runner the pages of each source, without any HTTP."""

    def __init__(self, pages: dict[str, list[CrawlPage]], errors: dict[str, list[str]] | None = None) -> None:
        self._pages = pages
        self._errors = errors or {}
        self.crawled: list[str] = []

    def crawl(self, source: Source) -> CrawlResult:
        self.crawled.append(source.name)
        result = CrawlResult(source_name=source.name)
        result.pages.extend(self._pages.get(source.name, []))
        result.errors.extend(self._errors.get(source.name, []))
        return result


def make_source(name: str = PROVIDER, base_url: str = "https://example.gov/open-grant") -> Source:
    return Source(
        name=name,
        base_url=base_url,
        country="Netherlands",
        trust_level="official",
        allowed_path_prefixes=("/open-grant",),
        crawl_depth=1,
    )


def make_page(
    text: str = PAGE_TEXT,
    url: str = "https://example.gov/open-grant",
    sha: str = "hash-one",
    title: str = "OPEN GRANT 2026",
) -> CrawlPage:
    return CrawlPage(
        url=url,
        final_url=url,
        title=title,
        text=text,
        sha256=sha,
        fetched_at="2026-10-21T10:00:00",
        etag='"e1"',
    )


def run(database: Database, pages: list[CrawlPage], replies) -> tuple[object, list]:
    """Run the catalog over one source and return (stats, events)."""
    events: list = []
    runner = CatalogRunner(
        database,
        _FakeGateway(replies),
        sources=[make_source()],
        crawler=_FakeCrawler({PROVIDER: pages}),
        progress=events.append,
    )
    return runner.run(), events


def only_record(database: Database) -> dict:
    records = list(database.catalog_records())
    assert len(records) == 1
    return records[0]


# -- one page ---------------------------------------------------------------


def test_a_verified_page_creates_a_catalog_record(temp_db: Database) -> None:
    stats, _events = run(temp_db, [make_page()], _reply(PROPOSAL))

    assert stats.pages_read == 1
    assert stats.records_created == 1
    record = only_record(temp_db)
    assert record["title"] == "OPEN GRANT 2026"
    assert record["provider"] == PROVIDER
    assert record["provider_domain"] == "example.gov"
    assert record["level"] == "master's degrees"
    assert record["countries"] == "Netherlands"
    assert record["fields_of_study"] == "economics, public policy"
    assert record["funding_type"] == "fully funded tuition"
    assert record["amount_text"] == "EUR 1 200"
    assert record["deadline_text"] == "5 November 2026"
    assert record["deadline_date"] == "2026-11-05"
    assert record["language_req"] == "IELTS 6.5"
    assert record["apply_url"] == "https://example.gov/open-grant/apply"
    assert record["canonical_key"] == canonical_key("OPEN GRANT 2026", "example.gov")
    assert record["data"]["values"]["deadline"] == "5 November 2026"


def test_a_record_keeps_the_page_behind_it(temp_db: Database) -> None:
    run(temp_db, [make_page()], _reply(PROPOSAL))
    record = only_record(temp_db)
    sources = temp_db.sources_for(int(record["id"]))
    assert len(sources) == 1
    assert sources[0]["source_url"] == "https://example.gov/open-grant"
    assert sources[0]["sha256"] == "hash-one"
    assert sources[0]["etag"] == '"e1"'
    assert sources[0]["provider"] == PROVIDER
    assert sources[0]["trust_level"] == "official"


def test_the_page_text_is_the_untrusted_block_in_the_prompt(temp_db: Database) -> None:
    gateway = _FakeGateway(_reply(PROPOSAL))
    CatalogRunner(
        temp_db,
        gateway,
        sources=[make_source()],
        crawler=_FakeCrawler({PROVIDER: [make_page()]}),
    ).run()
    prompt = gateway.prompts[0]
    assert "<<<PAGE>>>" in prompt
    assert "untrusted third-party web content" in prompt
    assert "OPEN GRANT 2026" in prompt


# -- honesty ----------------------------------------------------------------


def test_a_value_not_on_the_page_is_never_stored(temp_db: Database) -> None:
    invented = dict(PROPOSAL)
    invented["deadline"] = "1 December 2026"       # not on the page
    invented["stipend"] = "EUR 5 000"              # not on the page
    run(temp_db, [make_page()], _reply(invented))

    record = only_record(temp_db)
    assert record["deadline_text"] == ""
    assert record["amount_text"] == ""
    assert record["deadline_date"] is None
    unknown = record["data"]["unknown"]
    assert "deadline" in unknown
    assert "stipend" in unknown
    assert "stipend" not in record["data"]["values"]


def test_a_record_with_nothing_verified_is_not_saved(temp_db: Database) -> None:
    invented = {"title": "A Scholarship That Is Not On This Page"}
    stats, _events = run(temp_db, [make_page()], _reply(invented))
    assert stats.records == 0
    assert list(temp_db.catalog_records()) == []


def test_a_field_outside_the_schema_is_ignored(temp_db: Database) -> None:
    reply = dict(PROPOSAL)
    reply["guaranteed_admission"] = "yes"
    run(temp_db, [make_page()], _reply(reply))
    record = only_record(temp_db)
    assert "guaranteed_admission" not in record["data"]["values"]
    assert any("unsupported fields" in warning for warning in record["data"]["warnings"])


def test_a_date_with_two_dates_in_one_phrase_gets_no_deadline_date(temp_db: Database) -> None:
    text = PAGE_TEXT.replace(
        "Deadline: 5 November 2026",
        "Applications: opens 1 August 2026 and closes 15 January 2027",
    )
    proposal = dict(PROPOSAL)
    proposal["deadline"] = "opens 1 August 2026 and closes 15 January 2027"
    run(temp_db, [make_page(text)], _reply(proposal))
    record = only_record(temp_db)
    assert record["deadline_text"] == "opens 1 August 2026 and closes 15 January 2027"
    assert record["deadline_date"] is None, "two dates are not one deadline"


def test_an_ambiguous_numeric_date_gets_no_deadline_date(temp_db: Database) -> None:
    text = PAGE_TEXT.replace("5 November 2026", "05/11/2026")
    proposal = dict(PROPOSAL, deadline="05/11/2026")
    run(temp_db, [make_page(text)], _reply(proposal))
    record = only_record(temp_db)
    assert record["deadline_text"] == "05/11/2026"
    assert record["deadline_date"] is None, "05/11 could be May or November"


# -- normalisation ----------------------------------------------------------


def test_a_date_spelled_differently_verifies_by_value(temp_db: Database) -> None:
    proposal = dict(PROPOSAL, deadline="5th November 2026")
    run(temp_db, [make_page()], _reply(proposal))
    record = only_record(temp_db)
    assert record["deadline_text"] == "5th November 2026"
    assert record["deadline_date"] == "2026-11-05"


def test_a_dash_and_quote_style_does_not_block_a_value(temp_db: Database) -> None:
    text = PAGE_TEXT.replace(
        "Deadline: 5 November 2026", "Deadline \u2014 5 November 2026"
    ).replace("economics", "\u201ceconomics\u201d")
    proposal = dict(
        PROPOSAL,
        deadline="Deadline - 5 November 2026",
        disciplines='"economics", public policy',
    )
    run(temp_db, [make_page(text)], _reply(proposal))
    record = only_record(temp_db)
    assert record["deadline_text"] == "Deadline - 5 November 2026"
    assert record["fields_of_study"].startswith('"economics"')


def test_a_hyphenated_line_break_does_not_block_a_value(temp_db: Database) -> None:
    text = PAGE_TEXT.replace("Funding:", "Fund-\ning:")
    proposal = dict(PROPOSAL, funding_coverage="Funding: fully funded tuition")
    run(temp_db, [make_page(text)], _reply(proposal))
    record = only_record(temp_db)
    assert record["funding_type"] == "Funding: fully funded tuition"


# -- dedup and merge --------------------------------------------------------


def test_two_pages_of_one_scholarship_are_one_record(temp_db: Database) -> None:
    second = make_page(
        PAGE_TEXT.replace("Deadline: 5 November 2026\n", ""),
        url="https://example.gov/open-grant/how-to-apply",
        sha="hash-two",
    )
    proposals = [
        _reply({"title": "OPEN GRANT 2026", "deadline": "5 November 2026"}),
        _reply({"title": "Open Grant 2026", "funding_coverage": "fully funded tuition"}),
    ]
    stats, _events = run(temp_db, [make_page(), second], proposals)

    assert stats.records == 2  # two handled pages, one stored record
    record = only_record(temp_db)
    assert record["deadline_text"] == "5 November 2026"
    assert record["funding_type"] == "fully funded tuition"  # filled from page two
    assert len(temp_db.sources_for(int(record["id"]))) == 2


def test_a_differing_verified_value_is_kept_and_written_down(temp_db: Database) -> None:
    second = make_page(
        PAGE_TEXT.replace("5 November 2026", "12 December 2026"),
        url="https://example.gov/open-grant/another-page",
        sha="hash-two",
    )
    proposals = [
        _reply({"title": "OPEN GRANT 2026", "deadline": "5 November 2026"}),
        _reply({"title": "OPEN GRANT 2026", "deadline": "12 December 2026"}),
    ]
    run(temp_db, [make_page(), second], proposals)

    record = only_record(temp_db)
    assert record["deadline_text"] == "5 November 2026", "the first value is not overwritten"
    conflicts = record["data"]["conflicts"]["deadline"]
    assert conflicts[0]["kept"] == "5 November 2026"
    assert conflicts[0]["ignored"] == "12 December 2026"
    assert conflicts[0]["source"] == "https://example.gov/open-grant/another-page"


def test_the_same_page_twice_adds_no_duplicate_source(temp_db: Database) -> None:
    run(temp_db, [make_page(), make_page()], _reply(PROPOSAL))
    record = only_record(temp_db)
    assert len(temp_db.sources_for(int(record["id"]))) == 1


def test_a_title_with_different_punctuation_is_the_same_record(temp_db: Database) -> None:
    second = make_page(url="https://example.gov/open-grant/apply", sha="hash-two")
    run(
        temp_db,
        [make_page(), second],
        [_reply({"title": "OPEN GRANT 2026"}), _reply({"title": "Open-Grant 2026!"})],
    )
    assert len(list(temp_db.catalog_records())) == 1


def test_different_domains_are_different_records(temp_db: Database) -> None:
    other = make_page(url="https://other.example/open-grant", sha="hash-other")
    events: list = []
    runner = CatalogRunner(
        temp_db,
        _FakeGateway(_reply({"title": "OPEN GRANT 2026"})),
        sources=[make_source(), make_source(name="Other Portal", base_url="https://other.example/open-grant")],
        crawler=_FakeCrawler(
            {
                PROVIDER: [make_page()],
                "Other Portal": [other],
            }
        ),
        progress=events.append,
    )
    runner.run()
    assert len(list(temp_db.catalog_records())) == 2


def test_the_canonical_key_is_the_normalised_title_and_domain() -> None:
    assert canonical_key("OPEN GRANT 2026", "example.gov") == "example.gov|open grant 2026"
    assert canonical_key("Open-Grant   2026!", "example.gov") == "example.gov|open grant 2026"
    assert canonical_key("", "example.gov", "https://example.gov/x") == (
        "example.gov|url:https://example.gov/x"
    )
    assert domain_of("https://www.chevening.org/scholarships/") == "chevening.org"


# -- errors and control -----------------------------------------------------


def test_a_gateway_failure_is_counted_not_raised(temp_db: Database) -> None:
    from scholarpath.gateway.base import GatewayRateLimited

    class _BrokenGateway(ModelGateway):
        name = "broken"

        def complete(self, request):  # type: ignore[override]
            raise GatewayRateLimited("The model is rate-limited. Try again later.")

    events: list = []
    stats = CatalogRunner(
        temp_db,
        _BrokenGateway(),
        sources=[make_source()],
        crawler=_FakeCrawler({PROVIDER: [make_page()]}),
        progress=events.append,
    ).run()
    assert stats.errors == 1
    assert stats.records == 0
    assert any(event.kind == "error" for event in events)


def test_a_crawl_error_is_reported(temp_db: Database) -> None:
    events: list = []
    stats = CatalogRunner(
        temp_db,
        _FakeGateway(_reply(PROPOSAL)),
        sources=[make_source()],
        crawler=_FakeCrawler({}, {PROVIDER: ["https://example.gov/x - HTTP 500"]}),
        progress=events.append,
    ).run()
    assert stats.errors == 1
    assert any("HTTP 500" in event.message for event in events)


def test_cancelling_stops_before_the_next_page(temp_db: Database) -> None:
    second = make_page(url="https://example.gov/open-grant/two", sha="hash-two")
    events: list = []
    state = {"cancel": False}

    def cancel() -> bool:
        return state["cancel"]

    def progress(event) -> None:
        events.append(event)
        if event.kind == "record":
            state["cancel"] = True  # the student pressed Cancel mid-run

    stats = CatalogRunner(
        temp_db,
        _FakeGateway(_reply(PROPOSAL)),
        sources=[make_source()],
        crawler=_FakeCrawler({PROVIDER: [make_page(), second]}),
        cancel=cancel,
        progress=progress,
    ).run()
    assert stats.cancelled is True
    assert stats.records == 1
    assert len(list(temp_db.catalog_records())) == 1


def test_a_disabled_source_is_not_crawled(temp_db: Database) -> None:
    source = make_source()
    disabled = Source(
        name=source.name,
        base_url=source.base_url,
        country=source.country,
        trust_level=source.trust_level,
        allowed_path_prefixes=source.allowed_path_prefixes,
        crawl_depth=source.crawl_depth,
        enabled=False,
    )
    crawler = _FakeCrawler({PROVIDER: [make_page()]})
    stats = CatalogRunner(
        temp_db, _FakeGateway(_reply(PROPOSAL)), sources=[disabled], crawler=crawler
    ).run()
    assert stats.sources == 0
    assert crawler.crawled == []


def test_the_summary_counts_what_really_happened(temp_db: Database) -> None:
    stats, _events = run(temp_db, [make_page()], _reply(PROPOSAL))
    summary = stats.summary()
    assert "1 portal(s)" in summary
    assert "1 page(s) read" in summary
    assert "1 record(s) stored" in summary


def test_the_catalog_values_mapping_is_explicit() -> None:
    values = catalog_values(
        {
            "title": "T",
            "institution": "I",
            "degree_levels": "L",
            "host_country": "C",
            "disciplines": "F",
            "funding_coverage": "FT",
            "stipend": "A",
            "deadline": "D",
            "language_requirement": "LR",
            "application_url": "U",
        }
    )
    assert values == {
        "title": "T",
        "institution": "I",
        "level": "L",
        "countries": "C",
        "fields_of_study": "F",
        "funding_type": "FT",
        "amount_text": "A",
        "deadline_text": "D",
        "language_req": "LR",
        "apply_url": "U",
    }


# -- database migration -----------------------------------------------------

_OLD_SCHEMA = """
CREATE TABLE scholarship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    institution TEXT NOT NULL DEFAULT '',
    requested_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    page_sha256 TEXT NOT NULL,
    page_title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'page-verified',
    data TEXT NOT NULL DEFAULT '{}'
);
"""


def test_an_old_database_gains_the_catalog_columns(tmp_path) -> None:
    path = tmp_path / "old.db"
    connection = sqlite3.connect(str(path))
    connection.executescript(_OLD_SCHEMA)
    connection.execute(
        "INSERT INTO scholarship (created_at, title, requested_url, final_url, "
        "retrieved_at, page_sha256, page_title, data) VALUES "
        "('2026-01-01T00:00:00', 'Old record', 'https://example.edu/old', "
        "'https://example.edu/old', '2026-01-01T00:00:00', 'abc', 'Old page', "
        "'{\"values\": {\"title\": \"Old record\"}, \"unknown\": [], \"warnings\": []}')"
    )
    connection.commit()
    connection.close()

    database = Database(path)
    try:
        columns = {
            row[1]
            for row in database._connection.execute("PRAGMA table_info(scholarship)")
        }
        for column in (
            "level", "countries", "fields_of_study", "funding_type", "amount_text",
            "deadline_text", "deadline_date", "language_req", "apply_url",
            "canonical_key", "provider", "provider_domain",
        ):
            assert column in columns
        record = next(database.catalog_records())
        assert record["title"] == "Old record"
        assert record["deadline_date"] is None
        assert record["canonical_key"] == ""
    finally:
        database.close()


def test_source_conditions_are_read_back(temp_db: Database) -> None:
    record_id, _action = temp_db.upsert_catalog_record(
        values={"title": "OPEN GRANT 2026", "deadline": "5 November 2026"},
        unknown=[],
        warnings=[],
        source_url="https://example.gov/open-grant",
        final_url="https://example.gov/open-grant",
        retrieved_at="2026-10-21T10:00:00",
        page_sha256="hash-one",
        page_title="OPEN GRANT 2026",
        provider=PROVIDER,
        provider_domain="example.gov",
        etag='"e1"',
        last_modified="Wed, 21 Oct 2026 10:00:00 GMT",
    )
    assert record_id > 0
    assert temp_db.source_conditions() == {
        "https://example.gov/open-grant": ('"e1"', "Wed, 21 Oct 2026 10:00:00 GMT")
    }


def test_deleting_a_record_removes_its_sources(temp_db: Database) -> None:
    run(temp_db, [make_page()], _reply(PROPOSAL))
    record = only_record(temp_db)
    assert temp_db.delete_scholarship(int(record["id"])) is True
    assert temp_db.sources_for(int(record["id"])) == []
    assert list(temp_db.catalog_records()) == []

# -- the record card (Phase 3) ------------------------------------------------

def test_the_catalog_card_shows_the_kept_difference() -> None:
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from scholarpath.ui.catalog_page import RecordCard

    QApplication.instance() or QApplication([])
    record = {
        "id": 1,
        "title": "OPEN GRANT 2026",
        "provider": PROVIDER,
        "provider_domain": "example.gov",
        "retrieved_at": "2026-10-21T10:00:00",
        "deadline_text": "30 November 2026",
        "page_text": "Deadline: 30 November 2026",
        "data": {
            "values": {"deadline": "30 November 2026"},
            "last_diff": [
                {
                    "field": "deadline",
                    "old": "5 November 2026",
                    "new": "30 November 2026",
                    "evidence": "Deadline: 30 November 2026",
                }
            ],
        },
    }

    card = RecordCard(record, [])

    texts = " ".join(label.text() for label in card.findChildren(QLabel))
    buttons = [button.text() for button in card.findChildren(QPushButton)]
    assert "the page changed - 1 field(s) differ" in texts
    assert "was \"5 November 2026\"" in texts
    assert "Deadline: 30 November 2026" in texts
    assert "Show what changed" in buttons
