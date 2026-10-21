"""Re-checking saved records against the live page (G142)."""

from __future__ import annotations

from datetime import date

from scholarpath.recheck import (
    STATUS_CHANGED,
    STATUS_DEADLINE_PASSED,
    STATUS_UNCHANGED,
    STATUS_UNREACHABLE,
    RecheckStore,
    deadline_passed,
    recheck_record,
)
from scholarpath.sources import FetchError


class FakePage:
    def __init__(self, sha256: str) -> None:
        self.sha256 = sha256


def _record(**overrides) -> dict:
    record = {
        "id": 7,
        "requested_url": "https://university.edu/scholarship",
        "final_url": "https://university.edu/scholarship",
        "retrieved_at": "2026-10-01T10:00:00",
        "page_sha256": "abc123",
        "data": {"deadline": "5 November 2026"},
    }
    record.update(overrides)
    return record


def test_an_unchanged_page_is_reported_as_unchanged() -> None:
    result = recheck_record(
        _record(), fetch=lambda url, **kwargs: FakePage("abc123")
    )
    assert result.status == STATUS_UNCHANGED
    assert result.changed is False
    assert result.checked is True
    assert result.flag == "Unchanged"


def test_a_changed_page_is_flagged() -> None:
    result = recheck_record(
        _record(), fetch=lambda url, **kwargs: FakePage("different")
    )
    assert result.status == STATUS_CHANGED
    assert result.changed is True
    assert result.flag == "Page changed"
    assert "different" in result.detail


def test_a_passed_deadline_is_flagged() -> None:
    result = recheck_record(
        _record(data={"deadline": "5 November 2024"}),
        fetch=lambda url, **kwargs: FakePage("abc123"),
        today=date(2026, 10, 21),
    )
    assert result.status == STATUS_DEADLINE_PASSED
    assert result.deadline_passed is True
    assert result.flag == "Deadline passed"


def test_a_passed_deadline_and_a_changed_page_are_both_reported() -> None:
    result = recheck_record(
        _record(data={"deadline": "5 November 2024"}),
        fetch=lambda url, **kwargs: FakePage("different"),
        today=date(2026, 10, 21),
    )
    assert result.status == STATUS_DEADLINE_PASSED
    assert result.changed is True
    assert "changed" in result.detail


def test_an_unreachable_page_is_reported_honestly() -> None:
    def failing(url, **kwargs):
        raise FetchError("Could not reach that page: no route to host")

    result = recheck_record(_record(), fetch=failing)
    assert result.status == STATUS_UNREACHABLE
    assert result.checked is False
    assert result.flag == "Could not check"
    assert "no route" in result.detail


def test_a_record_without_an_address_is_reported() -> None:
    result = recheck_record(_record(final_url="", requested_url=""))
    assert result.status == STATUS_UNREACHABLE
    assert "no page address" in result.detail


def test_deadline_detection() -> None:
    assert deadline_passed("5 November 2024", date(2026, 10, 21)) is True
    assert deadline_passed("5 November 2027", date(2026, 10, 21)) is False
    assert deadline_passed("not a date", date(2026, 10, 21)) is None
    assert deadline_passed("November 2024", date(2026, 10, 21)) is None
    assert deadline_passed("", date(2026, 10, 21)) is None


def test_the_store_keeps_the_last_result_per_record() -> None:
    store = RecheckStore()
    first = recheck_record(
        _record(), fetch=lambda url, **kwargs: FakePage("abc123")
    )
    store.set(first)
    assert store.get(7) is first
    second = recheck_record(
        _record(), fetch=lambda url, **kwargs: FakePage("changed")
    )
    store.set(second)
    assert store.get(7) is second
    assert "changed" in store.summary()
    store.clear()
    assert store.get(7) is None
    assert store.summary() == ""


def test_the_eligibility_page_can_re_check_its_records(tmp_path, monkeypatch) -> None:
    """The button fetches the pages again and the card shows the flag."""
    from PySide6.QtWidgets import QApplication

    import scholarpath.ui.recheck as ui_recheck
    from scholarpath.storage import Database
    from scholarpath.ui.eligibility_page import EligibilityPage

    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "recheck.db")
    record_id = database.save_scholarship(
        values={"title": "Test Scholarship", "deadline": "5 November 2026"},
        unknown=[],
        requested_url="https://university.edu/scholarship",
        final_url="https://university.edu/scholarship",
        retrieved_at="2026-10-01T10:00:00",
        page_sha256="abc123",
        page_title="Test Scholarship",
        warnings=[],
    )

    class Page:
        sha256 = "changed"

    monkeypatch.setattr(ui_recheck, "fetch_page", lambda url, **kwargs: Page())
    store = RecheckStore()
    page = EligibilityPage(database, recheck_store=store)
    page._start_recheck()
    deadline = __import__("time").time() + 10
    while __import__("time").time() < deadline and not store.all():
        app.processEvents()
        __import__("time").sleep(0.02)
    app.processEvents()

    result = store.get(record_id)
    assert result is not None
    assert result.changed is True
    assert "changed" in page._recheck_status.text().casefold()
    database.close()
    page.close()
