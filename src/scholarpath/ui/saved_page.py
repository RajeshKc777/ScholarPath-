"""Saved Opportunities page (M6): saved list, side-by-side comparison, checklists.

Nothing auto-saves: records appear here only after an explicit user save.
Comparison is a side-by-side reading of requirement states - deterministic
labels, no scores, no "winner". Checklists are drafted only from the record's
verbatim values; ticks persist.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
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
from scholarpath.export import csv_text, ics_event_count, ics_text
from scholarpath.freshness import (
    STATE_EXPIRED,
    STATUS_CHANGED,
    STATUS_FAILED,
    STATUS_UNCHANGED,
    FieldDiff,
    RefreshResult,
    deadline_state,
)
from scholarpath.profiles import Profile
from scholarpath.recheck import RecheckStore
from scholarpath.research import draft_checklist
from scholarpath.storage import Database
from scholarpath.ui.freshness import DifferencePanel, RefreshWorker
from scholarpath.ui.recheck import RecheckWorker
from scholarpath.ui.warnings import WarningSignsPanel

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
        gateway=None,
        model: str | None = None,
        trusted_domains: tuple[str, ...] | list[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._compare_ids: set[int] = set()
        self._recheck = recheck_store or RecheckStore()
        self._worker: RecheckWorker | None = None
        self._refresh_worker: RefreshWorker | None = None
        self._refresh_results: dict[int, RefreshResult] = {}
        self._gateway = gateway
        self._model = model
        self._trusted_domains = tuple(trusted_domains or ())

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
            "Fetch the pages again - the saved records first, then the most "
            "recent ones - and show what changed, field by field."
        )
        self._recheck_button.clicked.connect(self._start_refresh)
        actions.addWidget(self._recheck_button)
        self._export_csv_button = QPushButton("Export CSV", self)
        self._export_csv_button.setObjectName("GhostButton")
        self._export_csv_button.setToolTip(
            "Write the saved list to a CSV file: the source URL, the deadline "
            "text exactly as the page wrote it, and the last verified date."
        )
        self._export_csv_button.clicked.connect(self._export_csv)
        actions.addWidget(self._export_csv_button)
        self._export_ics_button = QPushButton("Export calendar", self)
        self._export_ics_button.setObjectName("GhostButton")
        self._export_ics_button.setToolTip(
            "Write the saved list to a calendar file (.ics). Only records with "
            "a readable deadline become events."
        )
        self._export_ics_button.clicked.connect(self._export_ics)
        actions.addWidget(self._export_ics_button)
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

    # -- the freshness job (G152-G155) ---------------------------------------
    def _start_refresh(self) -> None:
        """Check the pages again: the saved records first, then recent ones."""
        if self._refresh_worker is not None and self._refresh_worker.isRunning():
            return
        records = list(self._database.catalog_records())
        if not records:
            self._recheck_status.setText("There are no records to check yet.")
            return
        self._recheck_button.setEnabled(False)
        self._recheck_status.setText("Checking the pages again\u2026")
        self._refresh_worker = RefreshWorker(
            self._database,
            gateway=self._gateway,
            model=self._model,
            max_records=20,
        )
        self._refresh_worker.checked.connect(self._on_refresh_result)
        self._refresh_worker.finished_run.connect(self._on_refresh_finished)
        self._refresh_worker.start()

    def _on_refresh_result(self, result: RefreshResult) -> None:
        self._refresh_results[int(result.scholarship_id)] = result

    def _on_refresh_finished(self, stats) -> None:
        self._refresh_worker = None
        self._recheck_button.setEnabled(True)
        self._recheck_status.setText(stats.summary() if stats else "")
        self.reload()

    # -- export (G157) -------------------------------------------------------
    def _saved_records(self) -> list[dict]:
        records = {int(row["id"]): row for row in self._database.catalog_records()}
        return [
            records[record_id]
            for record_id in self._database.saved_opportunity_ids()
            if record_id in records
        ]

    def _write_file(self, path: str, text: str) -> None:
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
        except OSError as exc:
            self._recheck_status.setText(f"The file could not be written: {exc}")
            return
        self._recheck_status.setText(f"Written: {path}")

    def _export_csv(self) -> None:
        records = self._saved_records()
        if not records:
            self._recheck_status.setText("There is nothing saved to export.")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export the saved list",
            str(Path.home() / "scholarpath-saved.csv"),
            "CSV files (*.csv)",
        )
        if not path:
            return
        self._write_file(path, csv_text(records))

    def _export_ics(self) -> None:
        records = self._saved_records()
        if not records:
            self._recheck_status.setText("There is nothing saved to export.")
            return
        events = ics_event_count(records)
        if not events:
            self._recheck_status.setText(
                "None of the saved records has a readable deadline, so there "
                "is nothing to put in a calendar."
            )
            return
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export the saved list as a calendar",
            str(Path.home() / "scholarpath-saved.ics"),
            "Calendar files (*.ics)",
        )
        if not path:
            return
        self._write_file(path, ics_text(records))

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

    # -- what the record says about itself (G154, G155) ---------------------
    def _state_line(self, record_id: int, record: dict) -> QWidget:
        """One line about the record's freshness: expired, changed, or checked."""
        holder = QWidget(self)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        data = record.get("data") or {}
        status = str(data.get("last_check_status") or "")
        checked_at = str(data.get("last_checked_at") or "")[:10]
        verified_on = str(record.get("retrieved_at") or "")[:10]
        detail = str(data.get("last_check_detail") or "")
        diffs = self._diffs(record_id, record)

        def line(text: str) -> QLabel:
            label = QLabel(text, holder)
            label.setObjectName("DocMeta")
            label.setWordWrap(True)
            if detail:
                label.setToolTip(detail)
            return label

        if status == STATUS_FAILED:
            row.addWidget(line(f"could not re-check, last verified {verified_on or 'unknown'}"))
        elif diffs:
            text = (
                f"the page changed - {len(diffs)} field(s) differ "
                f"(last verified {verified_on or 'unknown'})"
            )
            row.addWidget(line(text))
        elif status == STATUS_UNCHANGED and checked_at:
            row.addWidget(line(f"checked again on {checked_at} - unchanged"))
        elif verified_on:
            row.addWidget(line(f"last verified {verified_on}"))

        if deadline_state(record) == STATE_EXPIRED:
            chip = QLabel("EXPIRED", holder)
            chip.setObjectName("CapFail")
            row.addWidget(chip)
            note = QLabel(
                "The stored deadline lies before today. Check the page - the "
                "scholarship may have been re-opened.",
                holder,
            )
            note.setObjectName("StateWhat")
            note.setWordWrap(True)
            row.addWidget(note, 1)
        row.addStretch(1)
        return holder

    # -- what changed (G153) -------------------------------------------------
    def _diffs(self, record_id: int, record: dict) -> list[FieldDiff]:
        """The changed fields: this run's result first, then the stored copy."""
        refresh = self._refresh_results.get(int(record_id))
        if refresh is not None and refresh.status == STATUS_CHANGED and refresh.diffs:
            return refresh.diffs
        stored = (record.get("data") or {}).get("last_diff") or []
        diffs: list[FieldDiff] = []
        for item in stored:
            if not isinstance(item, dict):
                continue
            diffs.append(
                FieldDiff(
                    field=str(item.get("field") or ""),
                    old=str(item.get("old") or ""),
                    new=str(item.get("new") or ""),
                    evidence=str(item.get("evidence") or ""),
                )
            )
        return diffs

    def _difference_panel(self, record_id: int, record: dict, card: QWidget) -> QWidget:
        """The old value, the new value and the page text behind each change."""
        return DifferencePanel(
            record, diffs=self._diffs(record_id, record), parent=card
        )

    # -- the warning signs (G158) --------------------------------------------
    def _signs_panel(self, record_id: int, record: dict, card: QWidget) -> QWidget:
        """The warning signs of this record, and why each one is there."""
        return WarningSignsPanel(record, trusted_domains=self._trusted_domains, parent=card)

    def _build_card(self, report, record: dict) -> QFrame:
        card = QFrame(self)
        card.setObjectName("DocCard")
        column = QVBoxLayout(card)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)
        record_id = report.scholarship_id

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

        column.addWidget(self._state_line(record_id, record))
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

        column.addWidget(self._difference_panel(record_id, record, card))
        column.addWidget(self._signs_panel(record_id, record, card))

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
