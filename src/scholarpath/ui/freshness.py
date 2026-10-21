"""The background re-check job, off the UI thread (G152-G155).

The worker owns the whole run: it fetches each page again, compares the page
hash, re-reads a page that changed and keeps the old version. The UI only
hears about the results. `DifferencePanel` is the other half: the one widget
that shows what changed, used by every card that can show a re-checked record.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from scholarpath.freshness import FieldDiff, RefreshResult, RefreshRunner, RefreshStats
from scholarpath.gateway.base import ModelGateway
from scholarpath.storage import Database

logger = logging.getLogger("scholarpath.ui.freshness")


class RefreshWorker(QThread):
    """Re-checks records' pages and reports each result as it arrives."""

    checked = Signal(object)  # RefreshResult
    finished_run = Signal(object)  # RefreshStats

    def __init__(
        self,
        database: Database,
        gateway: ModelGateway | None = None,
        model: str | None = None,
        max_records: int = 20,
        fetch: Callable[..., object] | None = None,
        cancel: Callable[[], bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._gateway = gateway
        self._model = model
        self._max_records = max_records
        self._fetch = fetch
        self._cancel = cancel

    def run(self) -> None:
        runner = RefreshRunner(
            self._database,
            gateway=self._gateway,
            model=self._model,
            fetch=self._fetch,
            max_records=self._max_records,
            cancel=self._cancel,
            progress=self._emit,
        )
        stats = runner.run()
        self.finished_run.emit(stats)

    def _emit(self, result: RefreshResult) -> None:
        self.checked.emit(result)


class DifferencePanel(QWidget):
    """The old value, the new value and the page text behind each change.

    The difference is read from the record itself (``data["last_diff"]``), so
    it is still there after a restart; the full versions stay in the version
    table. A record with no kept difference builds nothing.
    """

    def __init__(
        self,
        record: dict,
        diffs: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        items = list(diffs or [])
        if not items:
            for item in (record.get("data") or {}).get("last_diff") or []:
                if isinstance(item, dict) and item.get("field"):
                    items.append(
                        FieldDiff(
                            field=str(item.get("field") or ""),
                            old=str(item.get("old") or ""),
                            new=str(item.get("new") or ""),
                            evidence=str(item.get("evidence") or ""),
                        )
                    )
        self.diffs = items
        if not items:
            return

        toggle = QPushButton("Show what changed", self)
        toggle.setObjectName("LinkButton")
        toggle.setCursor(Qt.PointingHandCursor)
        column.addWidget(toggle)

        panel = QWidget(self)
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(4)
        for diff in items:
            line = QLabel(
                f"{diff.label}: was \"{diff.old or '(nothing)'}\" \u2192 now "
                f"\"{diff.new}\"",
                panel,
            )
            line.setObjectName("StateWhat")
            line.setWordWrap(True)
            inner.addWidget(line)
            if diff.evidence:
                evidence = QLabel(f"the page says: {diff.evidence}", panel)
                evidence.setObjectName("DocMeta")
                evidence.setWordWrap(True)
                inner.addWidget(evidence)
        note = QLabel(
            "The older version is kept, so the previous wording can still be "
            "read.",
            panel,
        )
        note.setObjectName("DocMeta")
        note.setWordWrap(True)
        inner.addWidget(note)
        inner.addStretch(1)
        panel.setVisible(False)
        column.addWidget(panel)
        toggle.clicked.connect(lambda: panel.setVisible(not panel.isVisible()))
