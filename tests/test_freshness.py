"""The re-check job: unchanged, changed, failed - and what expiry means (G152-G155).

No network: the fetch is a fake that hands back a page (or fails), and the
model is a fake that proposes values. The real verification and storage code
does the rest.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from scholarpath.freshness import (
    STATE_EXPIRED,
    STATE_NO_DATE,
    STATE_OPEN,
    STATUS_CHANGED,
    STATUS_FAILED,
    STATUS_UNCHANGED,
    RefreshRunner,
    deadline_state,
    diff_values,
)
from scholarpath.gateway.base import ChatResponse, ModelGateway
from scholarpath.sources import Resource
from scholarpath.storage import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "freshness.db")
    yield database
    database.close()


def _reply(fields: dict[str, str | None]) -> str:
    return "```json\n" + json.dumps({"fields": fields}) + "\n```"


class _FakeGateway(ModelGateway):
    name = "fake"

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.prompts: list[str] = []

    def complete(self, request):  # type: ignore[override]
        self.prompts.append(request.messages[-1].content)
        return ChatResponse(text=self._reply, model="test-model")


def _resource(url: str, body: str, status: int = 200) -> Resource:
    return Resource(
        requested_url=url,
        final_url=url,
        status=status,
        content_type="text/html",
        charset="utf-8",
        body=body.encode("utf-8"),
    )


PAGE = """<html><head><title>OPEN GRANT 2026</title></head><body>
<p>OPEN GRANT 2026</p>
<p>Host country: Netherlands</p>
<p>Degree level: master's degrees</p>
<p>Deadline: 5 November 2026</p>
<p>Language requirement: IELTS 6.5</p>
</body></html>
"""

NEW_PAGE = """<html><head><title>OPEN GRANT 2026</title></head><body>
<p>OPEN GRANT 2026</p>
<p>Host country: Netherlands</p>
<p>Degree level: master's degrees</p>
<p>Deadline: 30 November 2026</p>
<p>Language requirement: IELTS 7.0</p>
</body></html>
"""

PROPOSAL = {
    "title": "OPEN GRANT 2026",
    "host_country": "Netherlands",
    "degree_levels": "master's degrees",
    "deadline": "5 November 2026",
    "language_requirement": "IELTS 6.5",
}

NEW_PROPOSAL = {
    "title": "OPEN GRANT 2026",
    "host_country": "Netherlands",
    "degree_levels": "master's degrees",
    "deadline": "30 November 2026",
    "language_requirement": "IELTS 7.0",
}


def seed(
    db: Database,
    *,
    values: dict | None = None,
    url: str = "https://example.gov/open-grant",
    page_text: str = PAGE,
) -> int:
    record_id, _action = db.upsert_catalog_record(
        values=values or dict(PROPOSAL),
        unknown=[],
        warnings=[],
        source_url=url,
        final_url=url,
        retrieved_at="2026-10-01T09:00:00",
        page_sha256=hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
        page_title="OPEN GRANT 2026",
        provider="Example Portal",
        provider_domain="example.gov",
        page_text=page_text,
    )
    return record_id


# -- expiry (G154) ------------------------------------------------------------


def test_a_stored_date_before_today_means_expired() -> None:
    record = {"deadline_date": "2026-01-01"}
    assert deadline_state(record, date(2026, 10, 21)) == STATE_EXPIRED


def test_a_stored_date_after_today_means_open() -> None:
    record = {"deadline_date": "2026-12-01"}
    assert deadline_state(record, date(2026, 10, 21)) == STATE_OPEN


def test_a_record_without_a_stored_date_is_not_expired() -> None:
    assert deadline_state({"deadline_date": ""}, date(2026, 10, 21)) == STATE_NO_DATE
    assert deadline_state({}, date(2026, 10, 21)) == STATE_NO_DATE


def test_an_ambiguous_date_is_never_guessed_into_a_day(db: Database) -> None:
    # The page said "05/11/2026", which is not a single day, so nothing was
    # stored and nothing may be expired.
    record_id = seed(db, values={**PROPOSAL, "deadline": "05/11/2026"})
    record = db.record(record_id)
    assert record is not None
    assert record["deadline_date"] is None
    assert deadline_state(record, date(2026, 10, 21)) == STATE_NO_DATE


# -- the check (G152, G155) ---------------------------------------------------


def test_an_unchanged_page_is_reported_as_unchanged(db: Database) -> None:
    record_id = seed(db)
    runner = RefreshRunner(
        db,
        fetch=lambda url, **_kwargs: _resource(url, PAGE),
    )

    result = runner.check_record(db.record(record_id), today=date(2026, 10, 21))

    assert result.status == STATUS_UNCHANGED
    assert result.detail == "The page is unchanged."
    stored = db.record(record_id)
    assert stored is not None
    assert stored["data"]["last_check_status"] == STATUS_UNCHANGED


def test_a_failed_check_says_it_could_not_re_check(db: Database) -> None:
    record_id = seed(db)

    def _boom(url, **_kwargs):
        raise OSError("the server did not answer")

    runner = RefreshRunner(db, fetch=_boom)
    result = runner.check_record(db.record(record_id), today=date(2026, 10, 21))

    assert result.status == STATUS_FAILED
    assert result.detail == "could not re-check, last verified 2026-10-01"
    stored = db.record(record_id)
    assert stored is not None
    # The old copy is kept, and the record says it is not fresh.
    assert stored["data"]["values"]["deadline"] == "5 November 2026"
    assert stored["data"]["last_check_status"] == STATUS_FAILED
    assert "could not re-check" in stored["data"]["last_check_detail"]


def test_a_server_that_says_not_modified_means_unchanged(db: Database) -> None:
    record_id = seed(db)
    runner = RefreshRunner(
        db,
        fetch=lambda url, **_kwargs: _resource(url, "", status=304),
    )

    result = runner.check_record(db.record(record_id), today=date(2026, 10, 21))

    assert result.status == STATUS_UNCHANGED


def test_a_changed_page_is_read_again_and_both_versions_are_kept(db: Database) -> None:
    record_id = seed(db)
    gateway = _FakeGateway(_reply(NEW_PROPOSAL))
    runner = RefreshRunner(
        db,
        gateway=gateway,
        fetch=lambda url, **_kwargs: _resource(url, NEW_PAGE),
    )

    result = runner.check_record(db.record(record_id), today=date(2026, 10, 21))

    assert result.status == STATUS_CHANGED
    changed = {diff.field: (diff.old, diff.new) for diff in result.diffs}
    assert changed["deadline"] == ("5 November 2026", "30 November 2026")
    assert changed["language_requirement"] == ("IELTS 6.5", "IELTS 7.0")
    # The new value comes with the page text it was taken from.
    deadline_diff = [d for d in result.diffs if d.field == "deadline"][0]
    assert "30 November 2026" in deadline_diff.evidence

    versions = db.versions_for(record_id)
    assert len(versions) == 2
    assert versions[0]["values"]["deadline"] == "5 November 2026"
    assert versions[1]["values"]["deadline"] == "30 November 2026"

    stored = db.record(record_id)
    assert stored is not None
    assert stored["data"]["values"]["deadline"] == "30 November 2026"
    assert stored["deadline_text"] == "30 November 2026"
    assert stored["deadline_date"] == "2026-11-30"
    # The difference is kept with the record, so it survives a restart.
    kept = {item["field"]: item for item in stored["data"]["last_diff"]}
    assert kept["deadline"]["old"] == "5 November 2026"
    assert kept["deadline"]["new"] == "30 November 2026"
    assert "30 November 2026" in kept["deadline"]["evidence"]


def test_a_changed_page_that_cannot_be_re_read_keeps_the_old_copy(db: Database) -> None:
    record_id = seed(db)
    runner = RefreshRunner(
        db,
        gateway=None,  # no model service: the page cannot be re-read
        fetch=lambda url, **_kwargs: _resource(url, NEW_PAGE),
    )

    result = runner.check_record(db.record(record_id), today=date(2026, 10, 21))

    assert result.status == STATUS_FAILED
    assert "could not be re-read" in result.detail
    stored = db.record(record_id)
    assert stored is not None
    assert stored["data"]["values"]["deadline"] == "5 November 2026"
    # The record says the check did not succeed; the old copy is not fresh.
    assert stored["data"]["last_check_status"] == STATUS_FAILED
    assert db.versions_for(record_id) == []


def test_the_saved_records_are_checked_first(db: Database) -> None:
    first = seed(db, url="https://example.gov/first")
    second = seed(db, url="https://example.gov/second")
    db.save_opportunity(second)

    runner = RefreshRunner(db, fetch=lambda url, **_kwargs: _resource(url, PAGE))
    chosen = [int(row["id"]) for row in runner.records_to_check()]

    assert chosen[0] == second
    assert first in chosen


def test_the_run_counts_what_it_found(db: Database) -> None:
    seed(db)
    runner = RefreshRunner(db, fetch=lambda url, **_kwargs: _resource(url, PAGE))

    stats = runner.run(today=date(2026, 10, 21))

    assert stats.checked == 1
    assert stats.unchanged == 1
    assert "1 page(s) checked" in stats.summary()


# -- the difference (G153) ----------------------------------------------------


def test_the_difference_lists_only_the_fields_that_changed() -> None:
    diffs = diff_values(
        {"title": "A", "deadline": "1 May 2026", "host_country": "Nepal"},
        {"title": "A", "deadline": "2 May 2026", "host_country": "Nepal"},
        "The deadline is 2 May 2026.",
    )
    assert [diff.field for diff in diffs] == ["deadline"]
    assert diffs[0].old == "1 May 2026"
    assert diffs[0].new == "2 May 2026"
    assert "2 May 2026" in diffs[0].evidence


def test_a_field_the_new_page_no_longer_states_is_not_a_difference() -> None:
    diffs = diff_values({"stipend": "EUR 1000"}, {"title": "A"}, "")
    assert [diff.field for diff in diffs] == ["title"]
    assert diffs[0].old == ""
    assert diffs[0].new == "A"


# -- when a record is due (the schedule) --------------------------------------

def test_a_record_that_was_never_checked_is_due() -> None:
    from types import SimpleNamespace

    from scholarpath.ui.main_window import MainWindow

    fake = SimpleNamespace(
        _config=SimpleNamespace(freshness=SimpleNamespace(interval_hours=24))
    )
    assert MainWindow._records_due(fake, [{"data": {}}]) is True


def test_a_record_checked_within_the_interval_is_not_due() -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from scholarpath.ui.main_window import MainWindow

    fake = SimpleNamespace(
        _config=SimpleNamespace(freshness=SimpleNamespace(interval_hours=24))
    )
    fresh = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = "2020-01-01T00:00:00+00:00"

    assert MainWindow._records_due(fake, [{"data": {"last_checked_at": fresh}}]) is False
    assert MainWindow._records_due(fake, [{"data": {"last_checked_at": old}}]) is True
