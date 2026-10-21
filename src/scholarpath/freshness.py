"""Freshness: re-check a record's page and say honestly what changed (G152-G155).

A stored record is only worth something if it is still true. This module is the
job that keeps it true:

1. **Order** - the student's saved records first, then the most recent catalog
   records.
2. **Fetch** - the same guarded fetch the catalog uses: public addresses only,
   conditional requests with the stored ETag / Last-Modified, one request per
   second per host.
3. **Compare** - the sha256 of the page decides. The same hash means the page
   is unchanged; a different hash means it changed.
4. **Re-read** - a changed page is extracted again with the model, and every
   proposed value is verified word-for-word against the new page text
   (`research.build_scholarship_draft`). Only a value the new page states is
   stored.
5. **Keep both** - the previous version stays in `scholarship_version`, so the
   old value can still be read next to the new one.

Two rules the job never breaks:

- **Expiry is only ever a stored date.** A record is expired when its stored,
  unambiguous ``deadline_date`` lies before today. A page that words its date
  ambiguously keeps "no date"; it is never guessed into a day.
- **A failed check says so.** The record reads "could not re-check, last
  verified <date>", and the old copy is never presented as fresh.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Iterable

from scholarpath.crawler import HostThrottle
from scholarpath.extraction import parse_model_json
from scholarpath.gateway.base import ChatRequest, GatewayError, Message, ModelGateway
from scholarpath.research import (
    SCHOLARSHIP_FIELD_NAMES,
    build_scholarship_draft,
    build_scholarship_prompt,
)
from scholarpath.sources import Page, fetch_resource, page_from_resource
from scholarpath.storage import Database, catalog_columns

logger = logging.getLogger("scholarpath.freshness")

#: The deadline states a record can be in.
STATE_EXPIRED = "expired"
STATE_OPEN = "open"
STATE_NO_DATE = "no-date"

#: The result of checking one record's page.
STATUS_UNCHANGED = "unchanged"
STATUS_CHANGED = "changed"
STATUS_FAILED = "failed"

#: How the failure is worded, everywhere it is shown.
FAILED_DETAIL = "could not re-check, last verified {date}"

#: The fields the difference view compares, in the order they are shown.
DIFF_FIELDS = (
    "title",
    "institution",
    "host_country",
    "degree_levels",
    "disciplines",
    "funding_coverage",
    "stipend",
    "deadline",
    "language_requirement",
    "eligible_nationalities",
    "application_url",
)


def deadline_state(record: dict, today: date | None = None) -> str:
    """The record's deadline state, from the stored parsed date only.

    "expired" when the stored date is before today, "open" when it is not, and
    "no-date" when the page's wording was ambiguous or absent. The date is
    never guessed from the text here.
    """
    raw = str(record.get("deadline_date") or "").strip()
    if not raw:
        return STATE_NO_DATE
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return STATE_NO_DATE
    return STATE_EXPIRED if parsed < (today or date.today()) else STATE_OPEN


def last_verified_date(record: dict) -> str:
    """The day the stored copy was verified (its retrieval date)."""
    retrieved = str(record.get("retrieved_at") or "").strip()
    return retrieved[:10]


def _values_of(record: dict) -> dict[str, str]:
    data = record.get("data")
    if not isinstance(data, dict):
        return {}
    values = data.get("values")
    return dict(values) if isinstance(values, dict) else {}


def _snippet(text: str, value: str, limit: int = 200) -> str:
    """The sentence of the page that holds the value, for the difference view."""
    if not text or not value:
        return ""
    lowered = text.casefold()
    index = lowered.find(value.casefold())
    if index < 0:
        return ""
    start = max(0, index - 100)
    end = min(len(text), index + len(value) + 100)
    snippet = " ".join(text[start:end].split())
    return snippet[:limit]


@dataclass(frozen=True)
class FieldDiff:
    """One field that changed, with the page text the new value came from."""

    field: str
    old: str
    new: str
    evidence: str = ""

    @property
    def label(self) -> str:
        return self.field.replace("_", " ")


@dataclass
class RefreshResult:
    """What the re-check found for one record."""

    scholarship_id: int
    url: str
    status: str
    detail: str
    diffs: list[FieldDiff] = field(default_factory=list)
    checked_at: str = ""
    last_verified: str = ""
    deadline_state: str = STATE_NO_DATE
    version: int = 0

    @property
    def checked(self) -> bool:
        """True when the page was fetched and compared."""
        return self.status in (STATUS_UNCHANGED, STATUS_CHANGED)

    @property
    def changed(self) -> bool:
        return self.status == STATUS_CHANGED

    @property
    def flag(self) -> str:
        """A short label for the card."""
        if self.status == STATUS_CHANGED:
            count = len(self.diffs)
            return f"Page changed ({count} field(s))"
        if self.status == STATUS_FAILED:
            return "Could not re-check"
        return "Unchanged"

    @property
    def expired(self) -> bool:
        return self.deadline_state == STATE_EXPIRED


@dataclass
class RefreshStats:
    """The honest totals of a run."""

    checked: int = 0
    unchanged: int = 0
    changed: int = 0
    failed: int = 0
    expired: int = 0
    cancelled: bool = False

    def summary(self) -> str:
        parts = [f"{self.checked} page(s) checked"]
        if self.unchanged:
            parts.append(f"{self.unchanged} unchanged")
        if self.changed:
            parts.append(f"{self.changed} changed")
        if self.failed:
            parts.append(f"{self.failed} could not be checked")
        if self.expired:
            parts.append(f"{self.expired} expired")
        if self.cancelled:
            parts.append("stopped early")
        return " - ".join(parts)


def diff_values(
    old: dict[str, str],
    new: dict[str, str],
    page_text: str = "",
) -> list[FieldDiff]:
    """The fields whose wording changed between two versions."""
    diffs: list[FieldDiff] = []
    names = list(DIFF_FIELDS) + [
        name for name in new if name not in DIFF_FIELDS
    ]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        old_value = str(old.get(name) or "")
        new_value = str(new.get(name) or "")
        if not new_value or new_value == old_value:
            continue
        diffs.append(
            FieldDiff(
                field=name,
                old=old_value,
                new=new_value,
                evidence=_snippet(page_text, new_value),
            )
        )
    return diffs


class RefreshRunner:
    """Re-fetches records' pages and stores what changed."""

    def __init__(
        self,
        database: Database,
        gateway: ModelGateway | None = None,
        model: str | None = None,
        fetch: Callable[..., object] | None = None,
        throttle: HostThrottle | None = None,
        max_records: int = 20,
        cancel: Callable[[], bool] | None = None,
        progress: Callable[[RefreshResult], None] | None = None,
    ) -> None:
        self._database = database
        self._gateway = gateway
        self._model = model
        self._fetch = fetch
        self._throttle = throttle or HostThrottle()
        self._max_records = max_records
        self._cancel = cancel or (lambda: False)
        self.progress = progress or (lambda result: None)

    # -- what to check ----------------------------------------------------
    def records_to_check(self) -> list[dict]:
        """The saved records first, then the most recent catalog records."""
        records = {int(row["id"]): row for row in self._database.catalog_records()}
        chosen: list[dict] = []
        chosen_ids: set[int] = set()
        for record_id in self._database.saved_opportunity_ids():
            record = records.get(int(record_id))
            if record is not None:
                chosen.append(record)
                chosen_ids.add(int(record["id"]))
        for record in reversed(list(records.values())):
            if len(chosen) >= self._max_records:
                break
            if int(record["id"]) in chosen_ids:
                continue
            chosen.append(record)
            chosen_ids.add(int(record["id"]))
        return chosen

    # -- the run ----------------------------------------------------------
    def run(self, today: date | None = None) -> RefreshStats:
        stats = RefreshStats()
        for record in self.records_to_check():
            if self._cancel():
                stats.cancelled = True
                break
            result = self.check_record(record, today=today)
            stats.checked += 1
            if result.status == STATUS_UNCHANGED:
                stats.unchanged += 1
            elif result.status == STATUS_CHANGED:
                stats.changed += 1
            else:
                stats.failed += 1
            if result.expired:
                stats.expired += 1
            try:
                self.progress(result)
            except Exception:  # noqa: BLE001 - a broken listener must not stop the run
                logger.exception("the refresh progress listener failed")
        return stats

    def check_record(self, record: dict, today: date | None = None) -> RefreshResult:
        """Check one record's page and store what changed."""
        record_id = int(record.get("id") or 0)
        url = str(record.get("final_url") or record.get("requested_url") or "").strip()
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state = deadline_state(record, today)
        verified_on = last_verified_date(record)

        if not url:
            result = RefreshResult(
                scholarship_id=record_id,
                url="",
                status=STATUS_FAILED,
                detail=FAILED_DETAIL.format(date=verified_on or "unknown"),
                checked_at=checked_at,
                last_verified=verified_on,
                deadline_state=state,
            )
            self._database.mark_checked(
                record_id,
                checked_at=checked_at,
                status=STATUS_FAILED,
                detail=result.detail,
                deadline_state=state,
            )
            return result

        page, not_modified = self._fetch_page(url, record)
        if page is None and not not_modified:
            result = RefreshResult(
                scholarship_id=record_id,
                url=url,
                status=STATUS_FAILED,
                detail=FAILED_DETAIL.format(date=verified_on or "unknown"),
                checked_at=checked_at,
                last_verified=verified_on,
                deadline_state=state,
            )
            self._database.mark_checked(
                record_id,
                checked_at=checked_at,
                status=STATUS_FAILED,
                detail=result.detail,
                deadline_state=state,
            )
            return result

        if page is None:
            # The server said the stored copy is still current (304).
            self._database.mark_checked(
                record_id,
                checked_at=checked_at,
                status=STATUS_UNCHANGED,
                detail="The page is unchanged.",
                deadline_state=state,
            )
            return RefreshResult(
                scholarship_id=record_id,
                url=url,
                status=STATUS_UNCHANGED,
                detail="The page is unchanged.",
                checked_at=checked_at,
                last_verified=verified_on,
                deadline_state=state,
            )

        stored_hash = str(record.get("page_sha256") or "")
        if not stored_hash or page.sha256 == stored_hash:
            self._database.mark_checked(
                record_id,
                checked_at=checked_at,
                status=STATUS_UNCHANGED,
                detail="The page is unchanged.",
                deadline_state=state,
            )
            return RefreshResult(
                scholarship_id=record_id,
                url=url,
                status=STATUS_UNCHANGED,
                detail="The page is unchanged.",
                checked_at=checked_at,
                last_verified=verified_on,
                deadline_state=state,
            )

        return self._handle_change(record, page, today=today)

    # -- helpers ----------------------------------------------------------
    def _fetch_page(self, url: str, record: dict) -> tuple[Page | None, bool]:
        """The page again: (page, not_modified).

        ``not_modified`` is True when the server confirmed the stored copy is
        still current (HTTP 304); the page is then None.
        """
        conditions = self._database.source_conditions()
        etag, last_modified = conditions.get(url, ("", ""))
        host = url.split("/", 3)[2] if "://" in url else ""
        try:
            if host:
                self._throttle.wait(host)
            fetch = self._fetch or fetch_resource
            resource = fetch(
                url,
                etag=etag or None,
                last_modified=last_modified or None,
            )
        except Exception:  # noqa: BLE001 - a page that cannot be read is a fact
            logger.exception("re-checking %s failed", url)
            return None, False
        if getattr(resource, "not_modified", False):
            return None, True
        try:
            return page_from_resource(resource), False
        except Exception:  # noqa: BLE001 - an unreadable body is a failure, not a crash
            logger.exception("reading %s failed", url)
            return None, False

    def _handle_change(self, record: dict, page: Page, today: date | None) -> RefreshResult:
        """The page changed: re-read it, verify it, and keep both versions."""
        record_id = int(record.get("id") or 0)
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        old_values = _values_of(record)
        old_text = str(record.get("page_text") or "")

        verified = self._re_read(page)
        if verified is None:
            # The page changed but could not be re-read (no model service, or
            # the extraction failed). The old copy stays as it is, and the
            # record says so rather than pretending it is current.
            detail = (
                "The page changed, but it could not be re-read, so the stored "
                f"copy is still the one verified on {last_verified_date(record) or 'an earlier day'}."
            )
            self._database.mark_checked(
                record_id,
                checked_at=checked_at,
                status=STATUS_FAILED,
                detail=detail,
                deadline_state=deadline_state(record, today),
            )
            return RefreshResult(
                scholarship_id=record_id,
                url=str(record.get("final_url") or ""),
                status=STATUS_FAILED,
                detail=detail,
                checked_at=checked_at,
                last_verified=last_verified_date(record),
                deadline_state=deadline_state(record, today),
            )

        diffs = diff_values(old_values, verified, page.text)
        self._database.store_version(
            record_id,
            retrieved_at=str(record.get("retrieved_at") or ""),
            source_url=str(record.get("final_url") or record.get("requested_url") or ""),
            final_url=str(record.get("final_url") or ""),
            page_sha256=str(record.get("page_sha256") or ""),
            page_title=str(record.get("page_title") or ""),
            values=old_values,
            page_text=old_text,
        )
        version = self._database.store_version(
            record_id,
            retrieved_at=page.fetched_at,
            source_url=page.requested_url,
            final_url=page.final_url,
            page_sha256=page.sha256,
            page_title=page.title,
            values=verified,
            page_text=page.text,
        )

        merged = dict(old_values)
        merged.update(verified)
        state = deadline_state({**record, "deadline_date": _merged_deadline(merged)}, today)
        self._database.apply_refresh(
            record_id,
            values=verified,
            page_sha256=page.sha256,
            retrieved_at=page.fetched_at,
            page_text=page.text,
            page_title=page.title,
            final_url=page.final_url,
            checked_at=checked_at,
            deadline_state=state,
            status=STATUS_CHANGED,
            diffs=[
                {
                    "field": diff.field,
                    "old": diff.old,
                    "new": diff.new,
                    "evidence": diff.evidence,
                }
                for diff in diffs
            ],
        )

        detail = (
            f"{len(diffs)} field(s) changed since the copy verified on "
            f"{last_verified_date(record) or 'an earlier day'}."
        )
        return RefreshResult(
            scholarship_id=record_id,
            url=page.final_url,
            status=STATUS_CHANGED,
            detail=detail,
            diffs=diffs,
            checked_at=checked_at,
            last_verified=last_verified_date(record),
            deadline_state=state,
            version=version,
        )

    def _re_read(self, page: Page) -> dict[str, str] | None:
        """Extract and verify the page again. None when that was not possible."""
        if self._gateway is None:
            return None
        try:
            request = ChatRequest(
                messages=[
                    Message(role="user", content=build_scholarship_prompt(page))
                ],
                model=self._model,
            )
            response = self._gateway.complete(request)
            proposed = parse_model_json(
                response.text, allowed=SCHOLARSHIP_FIELD_NAMES, keep_unknown=True
            )
        except GatewayError:
            logger.exception("re-reading the page failed")
            return None
        except Exception:  # noqa: BLE001 - a failed read must not crash the run
            logger.exception("re-reading the page failed")
            return None
        draft = build_scholarship_draft(page, proposed)
        verified = draft.verified_values()
        return verified or None


def _merged_deadline(values: dict[str, str]) -> str:
    """The parsed deadline of a merged value set (empty when ambiguous)."""
    return str(catalog_columns(values).get("deadline_date") or "")
