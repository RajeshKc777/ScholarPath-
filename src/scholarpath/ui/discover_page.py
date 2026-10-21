"""Discover: search and filter the catalog, then check one record (G149, G150).

The page reads only what is already stored locally. It never searches the web,
never ranks students, and never changes a record while browsing. The
eligibility hand-off reuses the deterministic engine and the same report card
as the Eligibility page, so the two can never disagree.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from scholarpath.eligibility import evaluate
from scholarpath.profiles import stored_profile_payload
from scholarpath.search import (
    DEADLINE_ANY,
    DEADLINE_CHOICES,
    DEADLINE_CLOSED,
    DEADLINE_OPEN,
    DEADLINE_SOON,
    DEADLINE_UNKNOWN,
    LEVEL_ANY,
    LEVEL_CHOICES,
    SearchFilters,
    SearchHit,
    search_records,
    summary_line,
)
from scholarpath.storage import Database
from scholarpath.ui.eligibility_dialog import EligibilityDialog
from scholarpath.ui.warnings import WarningSignsPanel

logger = logging.getLogger("scholarpath.ui.discover")

#: What the deadline chip says, per state. Words, not colours alone.
_DEADLINE_CHIP = {
    DEADLINE_OPEN: ("OPEN", "CapLive"),
    DEADLINE_SOON: ("CLOSING SOON", "CapAmber"),
    DEADLINE_CLOSED: ("CLOSED", "CapFail"),
    DEADLINE_UNKNOWN: ("NO DATE", "CapGrey"),
}


class RecordCard(QFrame):
    """One search result: what the page states, and what you can do with it."""

    def __init__(
        self,
        hit: SearchHit,
        *,
        source_count: int,
        is_saved: bool,
        on_save: Callable[[int, bool], None],
        on_check: Callable[[dict], None],
        on_open: Callable[[str], None],
        trusted_domains=(),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.hit = hit
        self.record = hit.record
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(5)

        head = QHBoxLayout()
        title = QLabel(
            self.record.get("title")
            or self.record.get("page_title")
            or "(untitled record)",
            self,
        )
        title.setObjectName("DocName")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        provider = QLabel(
            str(self.record.get("provider") or self.record.get("provider_domain") or ""),
            self,
        )
        provider.setObjectName("DocMeta")
        head.addWidget(provider)
        column.addLayout(head)

        facts: list[str] = []
        if self.record.get("countries"):
            facts.append(f"Country: {self.record['countries']}")
        if self.record.get("level"):
            facts.append(f"Level: {self.record['level']}")
        if self.record.get("funding_type"):
            facts.append(f"Funding: {self.record['funding_type']}")
        if self.record.get("amount_text"):
            facts.append(f"Amount: {self.record['amount_text']}")
        if self.record.get("fields_of_study"):
            facts.append(f"Fields: {self.record['fields_of_study']}")
        if facts:
            line = QLabel("  \u00b7  ".join(facts), self)
            line.setObjectName("DocMeta")
            line.setWordWrap(True)
            column.addWidget(line)

        deadline_row = QHBoxLayout()
        deadline_row.setSpacing(8)
        chip_text, chip_name = _DEADLINE_CHIP.get(
            hit.deadline_state, ("NO DATE", "CapGrey")
        )
        chip = QLabel(chip_text, self)
        chip.setObjectName(chip_name)
        deadline_row.addWidget(chip, 0, Qt.AlignTop)
        phrase = QLabel(hit.deadline_phrase, self)
        phrase.setObjectName("DocMeta")
        phrase.setWordWrap(True)
        deadline_row.addWidget(phrase, 1)
        column.addLayout(deadline_row)
        if self.record.get("deadline_text"):
            written = QLabel(
                f'The page says: "{self.record["deadline_text"]}"', self
            )
            written.setObjectName("StateWhat")
            written.setWordWrap(True)
            column.addWidget(written)

        conflicts = (self.record.get("data") or {}).get("conflicts") or {}
        if conflicts:
            warn = QLabel(
                "Two pages state different values for: "
                + ", ".join(sorted(conflicts))
                + ". The value verified first was kept.",
                self,
            )
            warn.setObjectName("DocMeta")
            warn.setWordWrap(True)
            column.addWidget(warn)

        column.addWidget(
            WarningSignsPanel(
                self.record,
                trusted_domains=trusted_domains,
                parent=self,
            )
        )

        foot = QHBoxLayout()
        pages = QLabel(f"{source_count} page(s) behind this record", self)
        pages.setObjectName("DocMeta")
        foot.addWidget(pages)
        foot.addStretch(1)

        check = QPushButton("Check against my profile", self)
        check.setObjectName("LinkButton")
        check.setCursor(Qt.PointingHandCursor)
        check.setToolTip(
            "Run the same rule-based checks as the Eligibility page: no model, "
            "no probabilities, honest unknowns."
        )
        check.clicked.connect(lambda: on_check(self.record))
        foot.addWidget(check)

        record_id = int(self.record.get("id", 0))
        save = QPushButton("Save \u2605" if not is_saved else "Saved \u2713 (remove)", self)
        save.setObjectName("LinkButton" if not is_saved else "GhostButton")
        save.setCursor(Qt.PointingHandCursor)
        save.setToolTip("Add to Saved Opportunities. Nothing is saved automatically.")
        save.clicked.connect(lambda: on_save(record_id, not is_saved))
        foot.addWidget(save)

        url = str(self.record.get("final_url") or "")
        if url:
            link = QPushButton("Open page", self)
            link.setObjectName("LinkButton")
            link.setCursor(Qt.PointingHandCursor)
            link.setToolTip(url)
            link.clicked.connect(lambda: on_open(url))
            foot.addWidget(link)
        column.addLayout(foot)


class DiscoverPage(QWidget):
    """Search box, filters and the matching records."""

    def __init__(
        self,
        database: Database,
        trusted_domains=(),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._trusted_domains = tuple(trusted_domains or ())
        self._dialog: EligibilityDialog | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Discover", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "Search the records your catalog already holds and filter them by "
            "what the pages state. Browsing changes nothing and the search never "
            "leaves this device. A match is not a verdict: press Check against "
            "my profile for the rule-based checks.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        # -- filters ---------------------------------------------------------
        first = QHBoxLayout()
        first.setSpacing(8)
        self._search = QLineEdit(self)
        self._search.setObjectName("PField")
        self._search.setPlaceholderText(
            "Search a title, country, field, funder, or an amount on the page..."
        )
        self._search.setClearButtonEnabled(True)
        first.addWidget(self._search, 1)

        self._level = QComboBox(self)
        self._level.setObjectName("PCombo")
        for value, label in LEVEL_CHOICES:
            self._level.addItem(label, value)
        first.addWidget(self._level)

        self._deadline = QComboBox(self)
        self._deadline.setObjectName("PCombo")
        for value, label in DEADLINE_CHOICES:
            self._deadline.addItem(label, value)
        first.addWidget(self._deadline)
        outer.addLayout(first)

        second = QHBoxLayout()
        second.setSpacing(8)
        self._country = QLineEdit(self)
        self._country.setObjectName("PField")
        self._country.setPlaceholderText("Country")
        second.addWidget(self._country)
        self._field = QLineEdit(self)
        self._field.setObjectName("PField")
        self._field.setPlaceholderText("Field of study")
        second.addWidget(self._field)
        self._provider = QComboBox(self)
        self._provider.setObjectName("PCombo")
        self._provider.setMinimumWidth(170)
        second.addWidget(self._provider)
        clear = QPushButton("Clear filters", self)
        clear.setObjectName("GhostButton")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(self._clear_filters)
        second.addWidget(clear)
        second.addStretch(1)
        outer.addLayout(second)

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

        self._search.textChanged.connect(self._on_filter_changed)
        self._country.textChanged.connect(self._on_filter_changed)
        self._field.textChanged.connect(self._on_filter_changed)
        self._level.currentIndexChanged.connect(self._on_filter_changed)
        self._deadline.currentIndexChanged.connect(self._on_filter_changed)
        self._provider.currentIndexChanged.connect(self._on_filter_changed)

        self.reload()

    # -- filters -----------------------------------------------------------
    def _on_filter_changed(self, *_args) -> None:
        self._apply()

    def _filters(self) -> SearchFilters:
        return SearchFilters(
            text=self._search.text(),
            level=str(self._level.currentData() or LEVEL_ANY),
            country=self._country.text(),
            field=self._field.text(),
            provider=str(self._provider.currentData() or ""),
            deadline=str(self._deadline.currentData() or DEADLINE_ANY),
        )

    def _clear_filters(self) -> None:
        for widget in (self._search, self._country, self._field):
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        for combo in (self._level, self._deadline, self._provider):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._apply()

    def _refresh_providers(self, records: list[dict]) -> None:
        """Keep the portal list in step without losing the current choice."""
        previous = str(self._provider.currentData() or "")
        names = sorted(
            {
                str(record.get("provider") or "").strip()
                for record in records
                if str(record.get("provider") or "").strip()
            },
            key=str.casefold,
        )
        self._provider.blockSignals(True)
        self._provider.clear()
        self._provider.addItem("Any portal", "")
        for name in names:
            self._provider.addItem(name, name)
        index = self._provider.findData(previous)
        self._provider.setCurrentIndex(index if index >= 0 else 0)
        self._provider.blockSignals(False)

    # -- results -----------------------------------------------------------
    def reload(self) -> None:
        """Re-read the catalog (a run or a save may have changed it)."""
        records = list(self._database.catalog_records())
        self._refresh_providers(records)
        self._apply(records)

    def _apply(self, records: list[dict] | None = None) -> None:
        if records is None:
            records = list(self._database.catalog_records())
        hits = search_records(records, self._filters())
        self._summary.setText(summary_line(len(records), hits))

        while self._list.count() > 1:  # keep the trailing stretch
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not records:
            placeholder = QLabel(
                "The catalog is empty. Run the Catalog page first: it reads the "
                "official portals and stores only what their pages state.",
                self,
            )
            placeholder.setObjectName("PageLead")
            placeholder.setWordWrap(True)
            self._list.insertWidget(0, placeholder)
            return
        if not hits:
            placeholder = QLabel(
                "No record matches these filters. Try fewer words, or press "
                "Clear filters.",
                self,
            )
            placeholder.setObjectName("PageLead")
            placeholder.setWordWrap(True)
            self._list.insertWidget(0, placeholder)
            return

        for hit in hits:
            record_id = int(hit.record.get("id", 0))
            card = RecordCard(
                hit,
                source_count=len(self._database.sources_for(record_id)),
                is_saved=self._database.is_saved(record_id),
                on_save=self._toggle_save,
                on_check=self._check,
                on_open=self._open,
                trusted_domains=self._trusted_domains,
                parent=self,
            )
            self._list.insertWidget(self._list.count() - 1, card)

    # -- actions -----------------------------------------------------------
    def _toggle_save(self, record_id: int, save: bool) -> None:
        if save:
            self._database.save_opportunity(record_id)
        else:
            self._database.unsave_opportunity(record_id)
        self.reload()

    def _check(self, record: dict) -> None:
        """Hand the record to the deterministic engine and show the same card."""
        payload = stored_profile_payload(self._database.load_profile())
        report = evaluate(payload, record)
        filled = any(str(value or "").strip() for value in payload.values())
        record_id = int(record.get("id", 0))
        dialog = EligibilityDialog(
            report,
            is_saved=self._database.is_saved(record_id),
            on_save=self._toggle_save,
            profile_empty=not filled,
            record=record,
            trusted_domains=self._trusted_domains,
            parent=self,
        )
        self._dialog = dialog
        dialog.exec()
        self._dialog = None

    def _open(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))
