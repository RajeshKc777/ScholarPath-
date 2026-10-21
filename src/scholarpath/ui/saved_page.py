"""Saved Opportunities page (M6): saved list, side-by-side comparison, checklists.

Nothing auto-saves: records appear here only after an explicit user save.
Comparison is a side-by-side reading of requirement states - deterministic
labels, no scores, no "winner". Checklists are drafted only from the record's
verbatim values; ticks persist.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scholarpath.eligibility import (
    NOT_SATISFIED,
    SATISFIED,
    STATE_LABELS,
    UNKNOWN,
    evaluate_all,
)
from scholarpath.profiles import Profile
from scholarpath.recheck import RecheckStore
from scholarpath.research import draft_checklist
from scholarpath.storage import Database
from scholarpath.ui.recheck import RecheckWorker

logger = logging.getLogger("scholarpath.ui.saved")

_STATE_CHIP = {
    SATISFIED: "CapLive",
    NOT_SATISFIED: "CapFail",
    UNKNOWN: "CapGrey",
    "manual": "CapAmber",
}

_MAX_COMPARE = 4


def _chip(state: str) -> QLabel:
    chip = QLabel(STATE_LABELS.get(state, state).title())
    chip.setObjectName(_STATE_CHIP.get(state, "CapGrey"))
    return chip


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


class ChecklistsPanel(QWidget):
    """Per-record checklist: verbatim-derived steps with persistent ticks."""

    def __init__(
        self,
        record_id: int,
        values: dict[str, str],
        database: Database,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database

        column = QVBoxLayout(self)
        column.setContentsMargins(20, 2, 0, 4)
        column.setSpacing(4)

        draft = draft_checklist(values)
        items = database.checklist_items(record_id)
        stored = {item["text"] for item in items}
        if draft and set(draft) != stored:
            # Regeneration keeps ticks for surviving texts and adds nothing new
            # beyond what the record's verbatim values imply.
            database.replace_checklist(record_id, draft)
            items = database.checklist_items(record_id)

        if not items:
            empty = QLabel(
                "The page does not list required documents or an application "
                "link, so no steps are invented here. Open the source page to "
                "see how it asks you to apply.",
                self,
            )
            empty.setObjectName("StateWhat")
            empty.setWordWrap(True)
            column.addWidget(empty)
            return

        note = QLabel(
            "Drafted from the record's verbatim values only \u2014 "
            "nothing invented.",
            self,
        )
        note.setObjectName("StateWhat")
        note.setWordWrap(True)
        column.addWidget(note)
        for item in items:
            box = QCheckBox(item["text"], self)
            box.setChecked(bool(item["done"]))
            box.toggled.connect(
                lambda checked, item_id=item["id"]:
                self._database.set_checklist_done(item_id, checked)
            )
            column.addWidget(box)


class SavedPage(QWidget):
    def __init__(
        self,
        database: Database,
        recheck_store: RecheckStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._compare_ids: set[int] = set()
        self._recheck = recheck_store or RecheckStore()
        self._worker: RecheckWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Saved Opportunities", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "Records you explicitly saved \u2014 nothing is auto-saved. Compare "
            "them side by side, and keep a per-record application checklist "
            "drafted from each page's own wording.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        actions = QHBoxLayout()
        self._compare_button = QPushButton("Compare selected", self)
        self._compare_button.setObjectName("PrimaryButton")
        self._compare_button.setEnabled(False)
        self._compare_button.clicked.connect(self._show_compare)
        actions.addWidget(self._compare_button)
        self._compare_hint = QLabel("Tick 2\u20134 records to compare.", self)
        self._compare_hint.setObjectName("PageLead")
        actions.addWidget(self._compare_hint)
        self._recheck_button = QPushButton("Re-check pages", self)
        self._recheck_button.setObjectName("GhostButton")
        self._recheck_button.setToolTip(
            "Fetch every saved record's page again and flag the ones that "
            "changed or whose deadline has passed."
        )
        self._recheck_button.clicked.connect(self._start_recheck)
        actions.addWidget(self._recheck_button)
        self._recheck_status = QLabel("", self)
        self._recheck_status.setObjectName("PageLead")
        self._recheck_status.setWordWrap(True)
        actions.addWidget(self._recheck_status, 1)
        actions.addStretch(1)
        outer.addLayout(actions)

        self._body: QVBoxLayout = QVBoxLayout()
        outer.addLayout(self._body, 1)

        self.reload()

    # -- data ---------------------------------------------------------------

    def _records(self) -> dict[int, dict]:
        return {int(row["id"]): row for row in self._database.scholarships()}

    def _profile_payload(self) -> dict:
        record = self._database.load_profile()
        if not record:
            return {}
        profile, _dropped = Profile.from_payload(record.get("data", {}))
        return profile.model_dump()

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    # -- lifecycle ------------------------------------------------------------

    def reload(self) -> None:
        self._compare_ids &= set(self._records())  # drop ticks of deleted records
        self._clear_body()
        self._compare_button.setVisible(True)
        self._compare_hint.setVisible(True)
        self._show_list()

    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                _delete_layout(item.layout())

    # -- list view ------------------------------------------------------------

    def _show_list(self) -> None:
        records = self._records()
        payload = self._profile_payload()
        ids = self._database.saved_opportunity_ids()
        saved = [records[sid] for sid in ids if sid in records]

        if not saved:
            placeholder = QLabel(
                "Nothing saved yet. Open Eligibility (or verify a page on the "
                "Scholarships page) and save the records that interest you.",
                self,
            )
            placeholder.setObjectName("PageLead")
            placeholder.setWordWrap(True)
            self._body.addWidget(placeholder)
            self._update_compare_actions()
            return

        for report in evaluate_all(payload, saved):
            card = self._build_card(report, records[report.scholarship_id])
            self._body.addWidget(card)
        filler = QWidget(self)
        self._body.addWidget(filler, 1)
        self._update_compare_actions()

    # -- re-check (G142) -----------------------------------------------------
    def _start_recheck(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        records = list(self._database.scholarships())
        if not records:
            self._recheck_status.setText("There are no records to check yet.")
            return
        self._recheck_button.setEnabled(False)
        self._recheck_status.setText("Checking the pages again\u2026")
        self._worker = RecheckWorker(records, self._recheck)
        self._worker.checked.connect(self._on_rechecked)
        self._worker.finished.connect(self._on_recheck_finished)
        self._worker.start()

    def _on_rechecked(self, results) -> None:
        self._recheck_status.setText(self._recheck.summary())
        self.reload()

    def _on_recheck_finished(self) -> None:
        self._worker = None
        self._recheck_button.setEnabled(True)

    def _update_compare_actions(self) -> None:
        count = len(self._compare_ids)
        self._compare_button.setEnabled(2 <= count <= 4)
        if count < 2:
            self._compare_hint.setText("Tick 2\u20134 records to compare.")
        elif count == _MAX_COMPARE:
            self._compare_hint.setText(
                f"{count} selected \u2014 the most the table can show."
            )
        else:
            self._compare_hint.setText(f"{count} selected \u2014 ready to compare.")

    def _build_card(self, report, record: dict) -> QFrame:
        card = QFrame(self)
        card.setObjectName("DocCard")
        column = QVBoxLayout(card)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)

        head = QHBoxLayout()
        name = QLabel(report.title, card)
        name.setObjectName("DocName")
        head.addWidget(name, 1)
        verdict = QLabel(_short(report.verdict(), 120), card)
        verdict.setObjectName("DocMeta")
        verdict.setWordWrap(True)
        head.addWidget(verdict)
        column.addLayout(head)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        saved_on = QLabel(f"saved {report.retrieved_at}", card)
        saved_on.setObjectName("DocMeta")
        actions.addWidget(saved_on)
        recheck = self._recheck.get(record_id)
        if recheck is not None:
            flag = QLabel(f"re-check: {recheck.flag}", card)
            flag.setObjectName("DocMeta")
            flag.setToolTip(recheck.detail)
            actions.addWidget(flag)
        actions.addStretch(1)

        record_id = report.scholarship_id
        compare_box = QCheckBox("Compare", card)
        compare_box.setChecked(record_id in self._compare_ids)
        compare_box.toggled.connect(
            lambda checked, rid=record_id: self._compare_changed(rid, checked)
        )
        actions.addWidget(compare_box)

        if report.source_url:
            link = QPushButton("Open source page", card)
            link.setObjectName("LinkButton")
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(
                lambda _checked=False, url=report.source_url: self._open_url(url)
            )
            actions.addWidget(link)

        remove = QPushButton("Remove from saved", card)
        remove.setObjectName("GhostButton")
        remove.clicked.connect(lambda: self._remove(record_id))
        actions.addWidget(remove)
        column.addLayout(actions)

        for result in report.requirements:
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(_chip(result.state))
            label = QLabel(
                f"{result.label}: {result.explanation}", card
            )
            label.setObjectName("StateWhy")
            label.setWordWrap(True)
            row.addWidget(label, 1)
            column.addLayout(row)

        toggle = QPushButton("Application checklist", card)
        toggle.setObjectName("LinkButton")
        toggle.setCursor(Qt.PointingHandCursor)
        panel = ChecklistsPanel(record_id, record["data"].get("values", {}), self._database, card)
        panel.setVisible(False)
        toggle.clicked.connect(lambda: panel.setVisible(not panel.isVisible()))
        column.addWidget(toggle)
        column.addWidget(panel)
        return card

    def _compare_changed(self, record_id: int, checked: bool) -> None:
        if checked:
            self._compare_ids.add(record_id)
        else:
            self._compare_ids.discard(record_id)
        self._update_compare_actions()

    def _remove(self, record_id: int) -> None:
        self._database.unsave_opportunity(record_id)
        self.reload()

    # -- compare view -----------------------------------------------------------

    def _show_compare(self) -> None:
        self._compare_button.setVisible(False)
        self._compare_hint.setVisible(False)
        self._clear_body()

        records = self._records()
        payload = self._profile_payload()
        chosen = [
            records[sid] for sid in self._database.saved_opportunity_ids()
            if sid in self._compare_ids and sid in records
        ]
        if len(chosen) < 2:
            self.reload()
            return
        reports = evaluate_all(payload, chosen)

        back = QPushButton("\u2190 Back to saved list", self)
        back.setObjectName("GhostButton")
        back.clicked.connect(self.reload)
        self._body.addWidget(back)

        note = QLabel(
            "Side-by-side reading of what each page says \u2014 a reading aid, "
            "not a ranking. Full explanations of every state are on the "
            "Eligibility page.",
            self,
        )
        note.setObjectName("PageLead")
        note.setWordWrap(True)
        self._body.addWidget(note)

        holder = QFrame(self)
        holder.setObjectName("PanelCard")
        holder.setLayout(_build_compare_grid(holder, reports, self._open_url))
        self._body.addWidget(holder)


def _build_compare_grid(
    parent: QWidget,
    reports: list,
    open_url: Callable[[str], None],
) -> QGridLayout:
    """Attributes as rows, records as columns. Deterministic, no scores."""
    grid = QGridLayout(parent)
    grid.setContentsMargins(14, 14, 14, 14)
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(10)

    for column_index, report in enumerate(reports):
        name = QLabel(_short(report.title, 60), parent)
        name.setObjectName("DocName")
        name.setWordWrap(True)
        grid.addWidget(name, 0, 1 + column_index)
        link = QPushButton("Source", parent)
        link.setObjectName("LinkButton")
        link.setCursor(Qt.PointingHandCursor)
        link.clicked.connect(
            lambda _checked=False, url=report.source_url: open_url(url)
        )
        grid.addWidget(link, 1, 1 + column_index)

    # Requirement-state rows: the same requirement in every record.
    for row_index, requirement in enumerate(reports[0].requirements):
        header = QLabel(requirement.label, parent)
        header.setObjectName("RowLabel")
        header.setWordWrap(True)
        grid.addWidget(header, 2 + row_index, 0)
        for column_index, report in enumerate(reports):
            grid.addWidget(
                _chip(report.requirements[row_index].state),
                2 + row_index,
                1 + column_index,
            )

    row_offset = 2 + len(reports[0].requirements)
    text_rows = (
        ("Verdict", "verdict"),
        ("Funding (page words)", "funding"),
        ("Stated deadline", "deadline"),
    )
    for offset, (label, kind) in enumerate(text_rows):
        header = QLabel(label, parent)
        header.setObjectName("RowLabel")
        header.setWordWrap(True)
        grid.addWidget(header, row_offset + offset, 0)
        for column_index, report in enumerate(reports):
            if kind == "verdict":
                text = _short(report.verdict(), 120)
            else:
                key = "funding_coverage" if kind == "funding" else "deadline"
                text = _short(report.values.get(key, "\u2014"), 110)
            cell = QLabel(text, parent)
            cell.setObjectName("StateWhy")
            cell.setWordWrap(True)
            grid.addWidget(cell, row_offset + offset, 1 + column_index)

    for column_index in range(1, len(reports) + 1):
        grid.setColumnStretch(column_index, 1)
    grid.setColumnStretch(0, 0)
    return grid


def _delete_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        child = item.layout()
        if child is not None:
            _delete_layout(child)
    layout.deleteLater()
