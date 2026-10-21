"""Re-checking saved records against the live page (G142).

Every saved record carries the address it came from, the hash of the page
text and the moment it was retrieved. This module fetches that page again
and reports, honestly:

- whether the page still looks the same (same sha256) or has changed;
- whether the stated deadline has already passed;
- whether the page could be checked at all (and why not).

Nothing is rewritten: a changed page is flagged, not silently updated, and a
deadline is read from the record exactly as it was stored.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable

from scholarpath.extraction import date_parts
from scholarpath.sources import FetchError, fetch_page

logger = logging.getLogger("scholarpath.recheck")

STATUS_UNCHANGED = "unchanged"
STATUS_CHANGED = "changed"
STATUS_UNREACHABLE = "unreachable"
STATUS_DEADLINE_PASSED = "deadline-passed"


@dataclass(frozen=True)
class RecheckResult:
    """What a re-check found for one record."""

    scholarship_id: int
    url: str
    status: str
    detail: str
    deadline: str = ""
    deadline_passed: bool = False
    retrieved_at: str = ""
    current_sha256: str = ""
    changed: bool = False

    @property
    def checked(self) -> bool:
        """True when the page was actually fetched and compared."""
        return self.status in (STATUS_UNCHANGED, STATUS_CHANGED, STATUS_DEADLINE_PASSED)

    @property
    def flag(self) -> str:
        """A short label for the card."""
        if self.status == STATUS_DEADLINE_PASSED:
            return "Deadline passed"
        if self.status == STATUS_CHANGED:
            return "Page changed"
        if self.status == STATUS_UNREACHABLE:
            return "Could not check"
        return "Unchanged"


def deadline_passed(text: str, today: date | None = None) -> bool | None:
    """True when the stated deadline is before today; None when unknown."""
    parts = date_parts(text)
    if not parts:
        return None
    year, month, day = parts
    if not (year and month and day):
        return None
    try:
        value = date(year, month, day)
    except ValueError:
        return None
    return value < (today or date.today())


def _record_data(record: dict) -> dict:
    data = record.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def recheck_record(
    record: dict,
    *,
    fetch: Callable[..., object] = fetch_page,
    today: date | None = None,
) -> RecheckResult:
    """Fetch one record's page again and report what changed."""
    scholarship_id = int(record.get("id") or 0)
    url = str(record.get("final_url") or record.get("requested_url") or "").strip()
    stored_hash = str(record.get("page_sha256") or "").strip()
    retrieved_at = str(record.get("retrieved_at") or "")
    deadline = str(_record_data(record).get("deadline") or "").strip()
    passed = deadline_passed(deadline, today)

    if not url:
        return RecheckResult(
            scholarship_id,
            url,
            STATUS_UNREACHABLE,
            "This record has no page address to check.",
            deadline,
            bool(passed),
            retrieved_at,
        )

    try:
        page = fetch(url)
    except FetchError as exc:
        return RecheckResult(
            scholarship_id,
            url,
            STATUS_UNREACHABLE,
            str(exc),
            deadline,
            bool(passed),
            retrieved_at,
        )
    except Exception as exc:  # noqa: BLE001 - a check must never crash the app
        logger.exception("re-check failed for %s", url)
        return RecheckResult(
            scholarship_id,
            url,
            STATUS_UNREACHABLE,
            "The page could not be checked.",
            deadline,
            bool(passed),
            retrieved_at,
        )

    current = str(getattr(page, "sha256", "") or "")
    changed = bool(stored_hash) and current != stored_hash

    if changed:
        status = STATUS_CHANGED
        detail = "The page is different from the copy that was saved."
    else:
        status = STATUS_UNCHANGED
        detail = "The page is unchanged."

    if passed:
        status = STATUS_DEADLINE_PASSED
        detail = "The stated deadline has passed."
        if changed:
            detail += " The page also changed since it was saved."

    return RecheckResult(
        scholarship_id,
        url,
        status,
        detail,
        deadline,
        bool(passed),
        retrieved_at,
        current,
        changed,
    )


class RecheckStore:
    """The last re-check result for each record, shared by the pages."""

    def __init__(self) -> None:
        self._results: dict[int, RecheckResult] = {}

    def set(self, result: RecheckResult) -> None:
        self._results[result.scholarship_id] = result

    def get(self, scholarship_id: int) -> RecheckResult | None:
        return self._results.get(int(scholarship_id))

    def all(self) -> dict[int, RecheckResult]:
        return dict(self._results)

    def clear(self) -> None:
        self._results.clear()

    def summary(self) -> str:
        """One line for the page header."""
        results = list(self._results.values())
        if not results:
            return ""
        changed = sum(1 for item in results if item.changed)
        passed = sum(1 for item in results if item.deadline_passed)
        unreachable = sum(1 for item in results if item.status == STATUS_UNREACHABLE)
        parts = []
        if changed:
            parts.append(f"{changed} page(s) changed")
        if passed:
            parts.append(f"{passed} deadline(s) passed")
        if unreachable:
            parts.append(f"{unreachable} could not be checked")
        if not parts:
            parts.append(f"{len(results)} page(s) unchanged")
        return ", ".join(parts)
