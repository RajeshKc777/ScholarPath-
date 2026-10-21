"""The Re-check action shared by the Eligibility and Saved pages (G142)."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QThread, Signal

from scholarpath.recheck import RecheckResult, RecheckStore, recheck_record
from scholarpath.sources import fetch_page

logger = logging.getLogger("scholarpath.ui.recheck")


class RecheckWorker(QThread):
    """Re-fetches pages off the UI thread and reports what changed."""

    checked = Signal(object)  # list[RecheckResult]

    def __init__(
        self,
        records: list[dict],
        store: RecheckStore,
        fetch: Callable[..., object] | None = None,
    ) -> None:
        super().__init__()
        self._records = records
        self._store = store
        self._fetch = fetch

    def run(self) -> None:
        # Resolved here, not at import time, so the fetcher can be replaced.
        fetch = self._fetch or fetch_page
        results: list[RecheckResult] = []
        for record in self._records:
            try:
                result = recheck_record(record, fetch=fetch)
            except Exception:  # noqa: BLE001 - one bad record must not stop the rest
                logger.exception("re-check failed for record %s", record.get("id"))
                continue
            self._store.set(result)
            results.append(result)
        self.checked.emit(results)


def recheck_label(result: RecheckResult | None) -> str:
    """The short chip text for a record."""
    if result is None:
        return ""
    return result.flag
