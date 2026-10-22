"""Scholarship research page: verify official pages, save page-verified records.

Honest scope (Milestone 4): there is **no scholarship search** in this build.
The user pastes the official page URL; the app reads it, the model proposes
fields, and only values that literally appear in the page text are offered.
The user ticks what to keep; the record is stored with its source URL,
retrieval time and page hash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from scholarpath.discovery import Discovery, discover
from scholarpath.gateway.base import ChatRequest, GatewayError, Message, ModelGateway
from scholarpath.research import (
    SCHOLARSHIP_FIELD_NAMES,
    SCHOLARSHIP_LABELS,
    ScholarshipDraft,
    build_scholarship_draft,
    build_scholarship_prompt,
    parse_model_json,
)
from scholarpath.sources import FetchError, fetch_page
from scholarpath.storage import Database
from scholarpath.ui.confirm_row import ConfirmRow

logger = logging.getLogger("scholarpath.ui.research")


class _DiscoveryWorker(QThread):
    """Look for scholarship links on one page, off the UI thread."""

    found = Signal(object, str)  # Discovery | None, error ("")

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            result = discover(self._url)
        except FetchError as exc:
            self.found.emit(None, str(exc))
        except Exception:  # noqa: BLE001 - discovery must never crash the app
            logger.exception("discovery crashed for %s", self._url)
            self.found.emit(None, "The page could not be searched for links.")
        else:
            self.found.emit(result, "")


class _VerifyWorker(QThread):
    """Fetch + gateway proposal, off the UI thread."""

    fetched = Signal(object, str)   # Page | None, error ("")
    drafted = Signal(object, str)   # ScholarshipDraft | None, error ("")

    def __init__(self, url: str, gateway: ModelGateway, model: str | None) -> None:
        super().__init__()
        self._url = url
        self._gateway = gateway
        self._model = model

    def run(self) -> None:
        try:
            page = fetch_page(self._url)
        except (FetchError, ValueError, OSError) as exc:
            logger.info("page fetch failed: %s", exc)
            self.fetched.emit(None, str(exc))
            return
        self.fetched.emit(page, "")

        request = ChatRequest(
            messages=[Message(role="user", content=build_scholarship_prompt(page))],
            model=self._model,
        )
        try:
            response = self._gateway.complete(request)
            proposed = parse_model_json(response.text, allowed=SCHOLARSHIP_FIELD_NAMES)
        except GatewayError as exc:
            logger.info("scholarship proposal failed: %s", exc.message)
            self.drafted.emit(None, exc.message)
            return
        except Exception:  # noqa: BLE001 - unexpected errors surface plainly
            logger.exception("scholarship extraction crashed")
            self.drafted.emit(None, "The extraction step failed unexpectedly.")
            return
        self.drafted.emit(build_scholarship_draft(page, proposed), "")


@dataclass
class PageVerification:
    """What the user chose to keep from one verified page."""

    requested_url: str
    final_url: str
    fetched_at: str
    page_sha256: str
    page_title: str
    values: dict[str, str]
    unknown: list[str]
    warnings: list[str]


class DraftCard(QFrame):
    """A fresh verification result: provenance, values to confirm, actions."""

    saved = Signal(object)   # PageVerification
    discarded = Signal()

    def __init__(
        self, draft: ScholarshipDraft, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._draft = draft
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)

        head = QHBoxLayout()
        name = QLabel(draft.page_title or "Scholarship page", self)
        name.setObjectName("DocName")
        head.addWidget(name, 1)
        meta = QLabel(
            f"final URL {draft.final_url}  \u00b7  retrieved {draft.fetched_at}  \u00b7  "
            f"page {draft.page_sha256[:12]}",
            self,
        )
        meta.setObjectName("DocMeta")
        meta.setWordWrap(True)
        head.addWidget(meta)
        column.addLayout(head)

        for warning in draft.warnings:
            warn = QLabel(warning, self)
            warn.setObjectName("DocMeta")
            warn.setWordWrap(True)
            column.addWidget(warn)

        if draft.page_excerpt:
            preview = QPlainTextEdit(self)
            preview.setObjectName("SourcePreview")
            preview.setReadOnly(True)
            preview.setFixedHeight(76)
            preview.setPlainText(draft.page_excerpt[:1800])
            column.addWidget(preview)

        if not draft.fields:
            note = QLabel(
                "The model proposed no scholarship fields from this page. If the "
                "page really is a scholarship page, try again later or store your "
                "own notes.",
                self,
            )
            note.setObjectName("DocMeta")
            note.setWordWrap(True)
            column.addWidget(note)
            discard = QPushButton("Discard", self)
            discard.setObjectName("GhostButton")
            discard.clicked.connect(self.discarded.emit)
            column.addWidget(discard)
            return

        column.addWidget(
            QLabel("Values found on the page \u2014 tick what to keep:", self)
        )
        self._rows: list[ConfirmRow] = []
        for proposal in draft.fields:
            row_widget = ConfirmRow(
                SCHOLARSHIP_LABELS.get(proposal.name, proposal.name),
                proposal.value,
                proposal.verified,
                proposal.rejected_reason,
                "page",
                self,
            )
            row_widget.field_name = proposal.name
            self._rows.append(row_widget)
            column.addWidget(row_widget)

        unverified = sum(1 for proposal in draft.fields if not proposal.verified)
        if unverified:
            warn = QLabel(
                f"{unverified} value(s) do not appear word-for-word on the page. "
                "Unticked unverifiable rows are never saved \u2014 they are reported "
                "as unknown instead.",
                self,
            )
            warn.setObjectName("DocMeta")
            warn.setWordWrap(True)
            column.addWidget(warn)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("Discard", self)
        cancel.setObjectName("GhostButton")
        cancel.clicked.connect(self.discarded.emit)
        footer.addWidget(cancel)
        save = QPushButton("Save checked values", self)
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._on_save)
        footer.addWidget(save)
        column.addLayout(footer)

    def _on_save(self) -> None:
        values: dict[str, str] = {}
        for row_widget in self._rows:
            if row_widget.check.isChecked():
                text = row_widget.edit.text().strip()
                if text:
                    values[row_widget.field_name] = text
        if not values:
            QMessageBox.information(
                self,
                "Nothing ticked",
                "Tick at least one value to save, or Discard to throw this away.",
            )
            return
        unknown = [
            proposal.name
            for proposal in self._draft.fields
            if not proposal.verified
        ]
        self.saved.emit(
            PageVerification(
                requested_url=self._draft.requested_url,
                final_url=self._draft.final_url,
                fetched_at=self._draft.fetched_at,
                page_sha256=self._draft.page_sha256,
                page_title=self._draft.page_title,
                values=values,
                unknown=unknown,
                warnings=list(self._draft.warnings),
            )
        )


class SavedScholarshipCard(QFrame):
    """A stored record: provenance, saved values, unknowns, save + delete."""

    deleted = Signal(int)
    save_toggled = Signal(int, bool)  # record id, want_saved

    def __init__(
        self,
        row: dict,
        is_saved: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._id = int(row["id"])
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)

        head = QHBoxLayout()
        name = QLabel(row["title"] or "(untitled record)", self)
        name.setObjectName("DocName")
        head.addWidget(name, 1)
        meta = QLabel(
            f"{row['final_url']}  \u00b7  retrieved {row['retrieved_at']}  \u00b7  "
            f"page {row['page_sha256'][:12]}",
            self,
        )
        meta.setObjectName("DocMeta")
        meta.setWordWrap(True)
        head.addWidget(meta)
        save = QPushButton("Save ★" if not is_saved else "Saved ✓ (remove)", self)
        save.setObjectName("LinkButton" if not is_saved else "GhostButton")
        save.setToolTip(
            "Add to Saved Opportunities. Nothing is ever saved automatically."
        )
        save.clicked.connect(
            lambda: self.save_toggled.emit(self._id, save.objectName() == "LinkButton")
        )
        head.addWidget(save)
        delete = QPushButton("Delete", self)
        delete.setObjectName("GhostButton")
        delete.clicked.connect(lambda: self.deleted.emit(self._id))
        head.addWidget(delete)
        column.addLayout(head)

        values: dict[str, str] = row["data"].get("values", {})
        unknown: list[str] = row["data"].get("unknown", [])
        for field_name, value in values.items():
            line = QHBoxLayout()
            line.setSpacing(8)
            label = QLabel(SCHOLARSHIP_LABELS.get(field_name, field_name), self)
            label.setMinimumWidth(150)
            line.addWidget(label)
            shown = QLabel(value, self)
            shown.setObjectName("DocMeta")
            shown.setWordWrap(True)
            line.addWidget(shown, 1)
            column.addLayout(line)

        if not values:
            empty = QLabel(
                "Every proposed field was unverifiable; nothing was stored.",
                self,
            )
            empty.setObjectName("DocMeta")
            empty.setWordWrap(True)
            column.addWidget(empty)

        if unknown:
            missing = QLabel(
                "Not found verbatim on the page (unknown, never guessed): "
                + ", ".join(SCHOLARSHIP_LABELS.get(name, name) for name in unknown),
                self,
            )
            missing.setObjectName("DocMeta")
            missing.setWordWrap(True)
            column.addWidget(missing)


class ResearchPage(QWidget):
    def __init__(
        self,
        database: Database,
        gateway: ModelGateway,
        model: str | None,
        on_saved: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._gateway = gateway
        self._model = model
        self._on_saved = on_saved
        self._worker: _VerifyWorker | None = None
        self._discovery_worker: _DiscoveryWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        lead = QLabel(
            "Paste an official scholarship page and the app reads it, or paste "
            "a site's scholarships/funding page and use Find pages to list the "
            "scholarship links that page itself publishes. Only text that "
            "literally appears on a page can be kept. (The chat can also "
            "search the web for you.)",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(lead)
        outer.addLayout(header)

        row = QHBoxLayout()
        self.url_input = QLineEdit(self)
        self.url_input.setObjectName("PField")
        self.url_input.setPlaceholderText("https://university.edu/scholarship\u2026")
        row.addWidget(self.url_input, 1)
        self.find_button = QPushButton("Find pages", self)
        self.find_button.setObjectName("GhostButton")
        self.find_button.setToolTip(
            "List the scholarship and funding links published on that page "
            "(same site only). Nothing is guessed: every link is read from the "
            "page itself."
        )
        self.find_button.clicked.connect(self._on_find)
        row.addWidget(self.find_button)
        self.read_button = QPushButton("Read page", self)
        self.read_button.setObjectName("PrimaryButton")
        self.read_button.clicked.connect(self._on_read)
        row.addWidget(self.read_button)
        outer.addLayout(row)

        self._status = QLabel("", self)
        self._status.setObjectName("PageLead")
        self._status.setWordWrap(True)
        outer.addWidget(self._status)

        # -- links found on the page (G134) -----------------------------------
        self._suggestions = QFrame(self)
        self._suggestions.setObjectName("PanelCard")
        suggestions_layout = QVBoxLayout(self._suggestions)
        suggestions_layout.setContentsMargins(12, 10, 12, 12)
        suggestions_layout.setSpacing(6)
        suggestions_title = QLabel("Links published on that page", self._suggestions)
        suggestions_title.setObjectName("CardTitle")
        suggestions_layout.addWidget(suggestions_title)
        self._suggestions_layout = QVBoxLayout()
        self._suggestions_layout.setSpacing(6)
        suggestions_layout.addLayout(self._suggestions_layout)
        self._suggestions.hide()
        outer.addWidget(self._suggestions)

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

    # -- finding links on a page (G134) --------------------------------------
    def _on_find(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.information(
                self,
                "No address",
                "Paste the page to look at first, for example a university's "
                "scholarships or funding page.",
            )
            return
        if self._discovery_worker is not None and self._discovery_worker.isRunning():
            return
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self, "Already working", "A page is still being read. One moment."
            )
            return
        self._clear_suggestions()
        self._status.setText("Looking for scholarship links on that page\u2026")
        self.find_button.setEnabled(False)
        self.read_button.setEnabled(False)
        self.url_input.setEnabled(False)
        self._discovery_worker = _DiscoveryWorker(url)
        self._discovery_worker.found.connect(self._on_discovered)
        self._discovery_worker.finished.connect(self._clear_discovery_worker)
        self._discovery_worker.start()

    def _clear_discovery_worker(self) -> None:
        self._discovery_worker = None

    def _on_discovered(self, result: Discovery | None, error: str) -> None:
        self.find_button.setEnabled(True)
        self.read_button.setEnabled(True)
        self.url_input.setEnabled(True)
        if error or result is None:
            self._status.setText("")
            QMessageBox.warning(
                self,
                "Could not look at that page",
                error or "The page is unreachable.",
            )
            return
        if result.empty:
            self._status.setText(
                "No scholarship links were published on that page. Try the "
                "site's own scholarships, funding or financial aid page."
            )
            return
        title = result.title or result.final_url
        self._status.setText(
            f"Found {len(result.candidates)} scholarship link(s) on {title!r}. "
            "Click one to read and verify it."
        )
        self._show_suggestions(result)

    def _show_suggestions(self, result: Discovery) -> None:
        self._clear_suggestions()
        for candidate in result.candidates:
            button = QPushButton(
                f"{candidate.label}\n{candidate.url}", self._suggestions
            )
            button.setObjectName("ActionTile")
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip("Read this page and verify its values")
            button.clicked.connect(
                lambda _checked=False, url=candidate.url: self._open_candidate(url)
            )
            self._suggestions_layout.addWidget(button)
        self._suggestions.show()

    def _clear_suggestions(self) -> None:
        while self._suggestions_layout.count():
            item = self._suggestions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._suggestions.hide()

    def _open_candidate(self, url: str) -> None:
        self.url_input.setText(url)
        self._clear_suggestions()
        self._on_read()

    # -- verification flow ---------------------------------------------------
    def _on_read(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.information(
                self, "No address", "Paste the official page address first."
            )
            return
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self, "Already working", "A page is still being read. One moment."
            )
            return
        self._status.setText("Reading the page\u2026")
        self.read_button.setEnabled(False)
        self.url_input.setEnabled(False)
        self._worker = _VerifyWorker(url, self._gateway, self._model)
        self._worker.fetched.connect(self._on_fetched)
        self._worker.drafted.connect(self._on_drafted)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _clear_worker(self) -> None:
        self._worker = None

    def _on_fetched(self, page: object | None, error: str) -> None:
        if error:
            self._reset_controls()
            self._status.setText("")
            QMessageBox.warning(
                self, "Could not read the page", error or "The page is unreachable."
            )
        elif page is not None:
            title = page.title or "the page"  # type: ignore[union-attr]
            self._status.setText(
                f"Read {title!r}. Asking the model to propose fields\u2026"
            )

    def _on_drafted(
        self, draft: ScholarshipDraft | None, error: str
    ) -> None:
        self._reset_controls()
        if error:
            self._status.setText("")
            QMessageBox.warning(
                self,
                "Extraction failed",
                f"{error}\n\nThe page was read, but the model could not propose "
                "fields. Nothing was invented or saved.",
            )
            return
        if draft is None:
            self._status.setText("")
            return
        verified = sum(1 for proposal in draft.fields if proposal.verified)
        self._status.setText(
            f"{len(draft.fields)} field(s) proposed, {verified} verbatim on the "
            "page. Untick what you do not trust, then Save."
        )
        self.reload(fresh_draft=draft)

    def _reset_controls(self) -> None:
        self.read_button.setEnabled(True)
        self.url_input.setEnabled(True)

    # -- list ----------------------------------------------------------------
    def reload(self, fresh_draft: ScholarshipDraft | None = None) -> None:
        """Rebuild the list; optionally prepend a fresh verification card."""
        while self._list.count() > 1:  # keep trailing stretch
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # detach now; deleteLater alone stays painted
                widget.deleteLater()
        rows = list(self._database.scholarships())
        if not rows and fresh_draft is None:
            placeholder = QLabel(
                "No saved records yet. Paste an official scholarship page above.",
                self,
            )
            placeholder.setObjectName("PageLead")
            self._list.insertWidget(0, placeholder)
        if fresh_draft is not None:
            card = DraftCard(fresh_draft, self)
            card.saved.connect(self._on_save_card)
            card.discarded.connect(self.reload)
            self._list.insertWidget(self._list.count() - 1, card)
        for row in rows:
            item = SavedScholarshipCard(
                row, is_saved=self._database.is_saved(int(row["id"])), parent=self
            )
            item.deleted.connect(self._on_delete)
            item.save_toggled.connect(self._on_save_toggle)
            self._list.insertWidget(self._list.count() - 1, item)

    def _on_save_toggle(self, record_id: int, want_saved: bool) -> None:
        if want_saved:
            self._database.save_opportunity(record_id)
        else:
            self._database.unsave_opportunity(record_id)
        self.reload()

    # -- persistence ---------------------------------------------------------
    def _on_save_card(self, verification: PageVerification) -> None:
        scholarship_id = self._database.save_scholarship(
            values=verification.values,
            unknown=verification.unknown,
            requested_url=verification.requested_url,
            final_url=verification.final_url,
            retrieved_at=verification.fetched_at,
            page_sha256=verification.page_sha256,
            page_title=verification.page_title,
            warnings=verification.warnings,
        )
        logger.info(
            "scholarship %d saved (%d field(s))", scholarship_id, len(verification.values)
        )
        self.url_input.clear()
        self._status.setText(
            f"Saved {len(verification.values)} value(s) with source URL, "
            "retrieval time and page hash."
        )
        if self._on_saved:
            self._on_saved()
        self.reload()

    def _on_delete(self, scholarship_id: int) -> None:
        self._database.delete_scholarship(scholarship_id)
        logger.info("scholarship %d deleted", scholarship_id)
        self.reload()

    def cancel_worker(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(2000)
