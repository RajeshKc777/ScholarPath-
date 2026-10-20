"""Eligibility page: deterministic checks of saved records against the profile.

No model, no probabilities. Every requirement row shows its state, why, and the
page evidence it came from. The verdict never claims eligibility - only
conflicts, open checks and "confirm on the official page".
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from scholarpath.eligibility import (
    MANUAL,
    NOT_SATISFIED,
    SATISFIED,
    STATE_LABELS,
    UNKNOWN,
    evaluate_all,
)
from scholarpath.profiles import Profile
from scholarpath.storage import Database

logger = logging.getLogger("scholarpath.ui.eligibility")

_STATE_CHIP = {
    SATISFIED: "CapLive",
    NOT_SATISFIED: "CapFail",
    UNKNOWN: "CapGrey",
    MANUAL: "CapAmber",
}


def _state_chip_name(state: str) -> str:
    return _STATE_CHIP.get(state, "CapGrey")


class RequirementRow(QWidget):
    def __init__(self, result, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(10)

        chip = QLabel(STATE_LABELS[result.state].upper(), self)
        chip.setObjectName(_state_chip_name(result.state))
        row.addWidget(chip, 0, Qt.AlignTop)

        words = QVBoxLayout()
        words.setSpacing(1)
        label = QLabel(result.label, self)
        label.setObjectName("RowLabel")
        words.addWidget(label)
        why = QLabel(result.explanation, self)
        why.setObjectName("StateWhy")
        why.setWordWrap(True)
        words.addWidget(why)
        if result.evidence:
            page_evidence = result.evidence
            if len(page_evidence) > 200:
                page_evidence = page_evidence[:200].rstrip() + " … (truncated)"
            what = QLabel(f'Page says: "{page_evidence}"', self)
            what.setObjectName("StateWhat")
            what.setWordWrap(True)
            words.addWidget(what)
        row.addLayout(words, 1)


class ReportCard(QFrame):
    def __init__(
        self,
        report,
        open_source: Callable[[str], None],
        on_save: Callable[[int, bool], None],
        is_saved: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report = report
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)

        head = QHBoxLayout()
        name = QLabel(report.title, self)
        name.setObjectName("DocName")
        head.addWidget(name, 1)
        verdict = QLabel(report.verdict(), self)
        verdict.setObjectName("DocMeta")
        verdict.setWordWrap(True)
        head.addWidget(verdict)
        column.addLayout(head)

        for result in report.requirements:
            row = RequirementRow(result, self)
            column.addWidget(row)

        foot = QHBoxLayout()
        meta = QLabel(f"record retrieved {report.retrieved_at}", self)
        meta.setObjectName("DocMeta")
        foot.addWidget(meta)
        foot.addStretch(1)
        record_id = report.scholarship_id
        save = QPushButton("Save ★" if not is_saved else "Saved ✓ (remove)", self)
        save.setObjectName("LinkButton" if not is_saved else "GhostButton")
        save.setCursor(Qt.PointingHandCursor)
        save.setToolTip(
            "Add to Saved Opportunities. Nothing is ever saved automatically."
        )
        save.clicked.connect(
            lambda: on_save(record_id, save.objectName() == "LinkButton")
        )
        foot.addWidget(save)
        if report.source_url:
            link = QPushButton("Open source page", self)
            link.setObjectName("LinkButton")
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(lambda: open_source(report.source_url))
            foot.addWidget(link)
        column.addLayout(foot)


class EligibilityPage(QWidget):
    def __init__(
        self,
        database: Database,
        on_open_profile: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._on_open_profile = on_open_profile

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Eligibility checks", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "Rule-based checks of your saved scholarship records against your "
            "local profile. No model and no probabilities: anything either side "
            "does not clearly state comes back unknown or needs checking.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        self._summary = QLabel("", self)
        self._summary.setObjectName("PageLead")
        self._summary.setWordWrap(True)
        outer.addWidget(self._summary)

        scroll = QScrollArea(self)
        scroll.setObjectName("DocScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setObjectName("DocBody")
        self._list = QVBoxLayout(holder)
        self._list.setContentsMargins(0, 0, 0, 12)
        self._list.setSpacing(12)
        self._list.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self.reload()

    def _profile_payload(self) -> dict:
        record = self._database.load_profile()
        if not record:
            return {}
        profile, _dropped = Profile.from_payload(record.get("data", {}))
        return profile.model_dump()

    def reload(self) -> None:
        while self._list.count() > 1:  # keep trailing stretch
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        rows = list(self._database.scholarships())
        payload = self._profile_payload()
        filled = [k for k, v in payload.items() if str(v or "").strip()]
        if not rows:
            placeholder = QLabel(
                "No saved scholarship records yet. Verify an official page on the "
                "Scholarships page first, then come back here.",
                self,
            )
            placeholder.setObjectName("PageLead")
            self._list.insertWidget(0, placeholder)
            self._summary.setText("")
            return
        if not filled:
            self._summary.setText(
                "Your profile is empty, so every requirement will read unknown. "
                "Fill in My Profile (or confirm values from documents) first."
            )
        else:
            pretty = {"degree_level": "degree", "gpa": "GPA"}
            shown = ", ".join(
                f"{pretty.get(k, k)}: {str(payload[k]).strip()}"
                for k in ("nationality", "degree_level", "ielts", "gpa")
                if str(payload.get(k, "")).strip()
            )
            self._summary.setText(f"Checking against your profile \u2014 {shown}.")
        reports = evaluate_all(payload, rows)
        for report in reports:
            card = ReportCard(
                report,
                self._open_url,
                self._toggle_save,
                is_saved=self._database.is_saved(report.scholarship_id),
            )
            self._list.insertWidget(self._list.count() - 1, card)

    def _toggle_save(self, record_id: int, save: bool) -> None:
        if save:
            self._database.save_opportunity(record_id)
        else:
            self._database.unsave_opportunity(record_id)
        self.reload()

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))
