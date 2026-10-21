"""One record's eligibility checks, opened from Discover (G150).

It reuses the same report card the Eligibility page draws, so the hand-off can
never say something the page would not say. No model is involved.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from scholarpath.eligibility import EligibilityReport
from scholarpath.ui.eligibility_page import ReportCard


def _open_url(url: str) -> None:
    if url:
        QDesktopServices.openUrl(QUrl(url))


class EligibilityDialog(QDialog):
    """The record's rule-based checks against the local profile."""

    def __init__(
        self,
        report: EligibilityReport,
        *,
        is_saved: bool = False,
        on_save: Callable[[int, bool], None] | None = None,
        profile_empty: bool = False,
        record: dict | None = None,
        trusted_domains=(),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Checks against your profile")
        self.setObjectName("EligibilityDialog")
        self.resize(720, 620)
        self._on_save = on_save or (lambda _id, _save: None)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)

        head = QVBoxLayout()
        head.setSpacing(3)
        title = QLabel(report.title or "(untitled record)", self)
        title.setObjectName("PageTitle2")
        title.setWordWrap(True)
        head.addWidget(title)
        verdict = QLabel(report.verdict(), self)
        verdict.setObjectName("PageLead")
        verdict.setWordWrap(True)
        head.addWidget(verdict)
        outer.addLayout(head)

        note = QLabel(
            "Rule-based checks only: the page's own wording against your local "
            "profile. Nothing here is a probability, and nothing is sent "
            "anywhere. Confirm every requirement on the official page before "
            "applying.",
            self,
        )
        note.setObjectName("DocMeta")
        note.setWordWrap(True)
        outer.addWidget(note)

        if profile_empty:
            empty = QLabel(
                "Your profile is empty, so every requirement will read unknown. "
                "Fill in My Profile first.",
                self,
            )
            empty.setObjectName("DocMeta")
            empty.setWordWrap(True)
            outer.addWidget(empty)

        card = ReportCard(
            report,
            _open_url,
            self._toggle_save,
            is_saved=is_saved,
            record=record,
            trusted_domains=trusted_domains,
            parent=self,
        )
        scroll = QScrollArea(self)
        scroll.setObjectName("DocScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setObjectName("DocBody")
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        layout.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        foot = QHBoxLayout()
        foot.addStretch(1)
        close = QPushButton("Close", self)
        close.setObjectName("GhostButton")
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        outer.addLayout(foot)

    def _toggle_save(self, record_id: int, save: bool) -> None:
        self._on_save(record_id, save)
