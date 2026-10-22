"""Verify a page the chat named, right there in the chat (G186).

The chat offers "Verify this page" under an official link. Pressing it used
to send the student to the Scholarship Pages page, which lost the
conversation. Now the page is read and checked **in place**: the values that
appear word-for-word on the page are listed, the ones the page does not
state are named as such, and the record can be saved to the catalog from the
reply itself.

Nothing is invented here. The worker proposes fields, the draft keeps only
the values that appear in the page text, and nothing is saved until the
student presses Save.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scholarpath.gateway.base import ModelGateway
from scholarpath.research import SCHOLARSHIP_LABELS, ScholarshipDraft
from scholarpath.storage import Database
from scholarpath.ui.verify_worker import VerifyWorker

logger = logging.getLogger("scholarpath.ui.chat_verify")


class VerifyPanel(QFrame):
    """One page, read and checked, shown inside a chat reply."""

    saved = Signal(int)   # the id of the saved record
    checked = Signal(bool)  # True when the page was read and checked

    def __init__(
        self,
        url: str,
        gateway: ModelGateway,
        model: str | None,
        database: Database,
        on_saved: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("VerifyPanel")
        self._url = url
        self._gateway = gateway
        self._model = model
        self._database = database
        self._on_saved = on_saved
        self._draft: ScholarshipDraft | None = None
        self._worker: VerifyWorker | None = None
        self._saved = False
        #: Whether the page was read and checked. The chat reads it too, so it
        #: can label the button without waiting for a signal.
        self.checked_ok = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._status = QLabel("Reading the page\u2026", self)
        self._status.setObjectName("VerifyStatus")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._values = QVBoxLayout()
        self._values.setSpacing(2)
        layout.addLayout(self._values)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._save = QPushButton("Save to catalog", self)
        self._save.setObjectName("PrimaryButton")
        self._save.setVisible(False)
        self._save.clicked.connect(self._on_save)
        buttons.addWidget(self._save)
        self._close = QPushButton("Close", self)
        self._close.setObjectName("GhostButton")
        self._close.clicked.connect(self.close_panel)
        buttons.addWidget(self._close)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._start()

    # -- the flow ------------------------------------------------------------
    def _start(self) -> None:
        """Read the page and check it, off the UI thread."""
        self._worker = VerifyWorker(self._url, self._gateway, self._model)
        self._worker.fetched.connect(self._on_fetched)
        self._worker.drafted.connect(self._on_drafted)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _clear_worker(self) -> None:
        self._worker = None

    def _on_fetched(self, page: object | None, error: str) -> None:
        if error:
            self._status.setText(
                f"Could not read the page: {error} Nothing was checked and "
                "nothing was saved."
            )
            self._save.setVisible(False)
            self.checked_ok = False
            self.checked.emit(False)
            return
        title = str(getattr(page, "title", "") or "the page")
        self._status.setText(
            f"Read \u201c{title}\u201d. Checking every value against the page\u2026"
        )

    def _on_drafted(self, draft: ScholarshipDraft | None, error: str) -> None:
        if error:
            self._status.setText(
                "The page was read, but the model could not propose fields: "
                f"{error} Nothing was invented and nothing was saved."
            )
            self._save.setVisible(False)
            self.checked_ok = False
            self.checked.emit(False)
            return
        if draft is None:
            self._status.setText(
                "The page was read, but it holds nothing this app can check. "
                "Nothing was saved."
            )
            self._save.setVisible(False)
            self.checked_ok = False
            self.checked.emit(False)
            return
        self._draft = draft
        self.checked_ok = True
        self.checked.emit(True)
        self._show(draft)

    def _show(self, draft: ScholarshipDraft) -> None:
        """Show what the page states and what it does not."""
        verified = draft.verified_values()
        total = len(draft.fields)
        title = draft.page_title or "the page"
        self._status.setText(
            f"Checked \u201c{title}\u201d: {len(verified)} of {total} proposed "
            "value(s) appear word-for-word on the page."
        )
        for proposal in draft.fields:
            label = SCHOLARSHIP_LABELS.get(proposal.name, proposal.name)
            if proposal.verified:
                text = f"{label}: {proposal.value}"
                name = "VerifyValue"
            else:
                text = (
                    f"{label}: not on the page word-for-word (not saved)"
                )
                name = "VerifyNote"
            line = QLabel(text, self)
            line.setObjectName(name)
            line.setWordWrap(True)
            self._values.addWidget(line)
        missing = draft.unknown_fields()
        if missing:
            self._status.setText(
                self._status.text()
                + f" {len(missing)} value(s) did not appear on the page and stay "
                "empty rather than being guessed."
            )
        if verified:
            self._save.setVisible(True)
            self._save.setToolTip(
                "Save the checked values to your catalog, with the source "
                "address, the time it was read and the page hash."
            )
        else:
            self._status.setText(
                self._status.text()
                + " Nothing on this page could be checked, so there is nothing "
                "to save."
            )

    def _on_save(self) -> None:
        """Save the checked values - only the ones the page really states."""
        draft = self._draft
        if draft is None or self._saved:
            return
        values = draft.verified_values()
        if not values:
            self._status.setText(
                "There is nothing that appears on the page, so nothing was saved."
            )
            self._save.setVisible(False)
            return
        record_id = self._database.save_scholarship(
            values=values,
            unknown=draft.unknown_fields(),
            requested_url=draft.requested_url,
            final_url=draft.final_url,
            retrieved_at=draft.fetched_at,
            page_sha256=draft.page_sha256,
            page_title=draft.page_title,
            warnings=list(draft.warnings),
        )
        self._saved = True
        self._save.setVisible(False)
        self._status.setText(
            f"Saved {len(values)} value(s) to your catalog, with the source "
            "address, the time it was read and the page hash."
        )
        logger.info(
            "chat verification saved record %d (%d value(s))", record_id, len(values)
        )
        self.saved.emit(record_id)
        if self._on_saved is not None:
            self._on_saved()

    # -- housekeeping --------------------------------------------------------
    def close_panel(self) -> None:
        """Hide the panel; the button above it stays available."""
        self.setVisible(False)

    def cancel(self) -> None:
        """Stop the worker when the window closes."""
        if self._worker is None or not self._worker.isRunning():
            return
        if not self._worker.wait(5000):
            logger.warning("the page verification did not stop in time")
            self._worker.terminate()
            self._worker.wait(1000)
