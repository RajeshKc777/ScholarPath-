"""Documents page: upload, read locally, extract fields, confirm each one.

The pipeline is honest by construction:
1. The file is parsed locally (text layer or Windows OCR).
2. One gateway call proposes fields.
3. Every proposal is verified against the document text and shown with a
   "found in document" / "not found in document" marker; only rows the user
   checks (and may have corrected) are merged into the profile.
Nothing reaches the profile without the user's explicit confirmation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
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

from scholarpath.documents import DocumentText, extract_text
from scholarpath.extraction import (
    FIELD_LABELS,
    ProfileDraft,
    build_draft,
    build_prompt,
    parse_model_json,
)
from scholarpath.gateway.base import ChatRequest, GatewayError, Message, ModelGateway
from scholarpath.profiles import Profile, merge_confirmed
from scholarpath.storage import Database
from scholarpath.ui.confirm_row import ConfirmRow

logger = logging.getLogger("scholarpath.documents")

SUPPORTED_FILES = (
    "Documents (*.pdf *.txt *.md *.png *.jpg *.jpeg *.bmp);;All files (*.*)"
)


class _IngestWorker(QThread):
    """Local parse + gateway proposal, off the UI thread."""

    parsed = Signal(object, str)     # DocumentText | None, error ("")
    proposed = Signal(object, str)   # ProfileDraft | None, error ("")

    def __init__(self, path: str, gateway: ModelGateway, model: str | None) -> None:
        super().__init__()
        self._path = path
        self._gateway = gateway
        self._model = model

    def run(self) -> None:
        logger.info("parsing document")
        try:
            document = extract_text(Path(self._path))
        except (ValueError, RuntimeError, OSError) as exc:
            logger.warning("document parse failed: %s", exc)
            self.parsed.emit(None, str(exc))
            return
        self.parsed.emit(document, "")
        if document.empty:
            self.proposed.emit(None, "")
            return

        request = ChatRequest(
            messages=[Message(role="user", content=build_prompt(document.text))],
            model=self._model,
        )
        try:
            response = self._gateway.complete(request)
            proposed = parse_model_json(response.text)
        except GatewayError as exc:
            logger.warning("extraction proposal failed: %s", exc.message)
            self.proposed.emit(None, exc.message)
            return
        except Exception:  # noqa: BLE001 - unexpected errors surface plainly
            logger.exception("extraction crashed")
            self.proposed.emit(None, "The extraction step failed unexpectedly.")
            return
        draft = build_draft(document.filename, document.text, proposed)
        if draft.fields:
            logger.info(
                "extraction proposed %d fields (%d verified)",
                len(draft.fields),
                sum(1 for f in draft.fields if f.verified),
            )
        self.proposed.emit(draft, "")


class DocumentCard(QFrame):
    """One uploaded document: provenance, preview, confirmation rows, actions."""

    confirm_requested = Signal(int, dict)  # database id, {field: value}
    deleted = Signal(int)

    def __init__(
        self,
        document_id: int,
        filename: str,
        document: DocumentText,
        draft: ProfileDraft | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._id = document_id
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)

        head = QHBoxLayout()
        name_label = QLabel(filename, self)
        name_label.setObjectName("DocName")
        head.addWidget(name_label, 1)
        details: list[str] = []
        details.append("read with Windows OCR" if document.ocr_used else "text layer")
        details.append(f"{len(document.text):,} characters")
        details += document.warnings
        meta = QLabel("  \u00b7  ".join(details), self)
        meta.setObjectName("DocMeta")
        meta.setWordWrap(True)
        head.addWidget(meta)
        delete = QPushButton("Delete", self)
        delete.setObjectName("GhostButton")
        delete.clicked.connect(lambda: self.deleted.emit(self._id))
        head.addWidget(delete)
        column.addLayout(head)

        preview = QPlainTextEdit(self)
        preview.setObjectName("SourcePreview")
        preview.setReadOnly(True)
        preview.setFixedHeight(76)
        preview.setPlainText(document.text.strip()[:2000] or "(no text could be read)")
        column.addWidget(preview)

        if draft is None or not draft.fields:
            note = QLabel(
                "No confirmable fields were proposed. The text is kept with this "
                "document record only.",
                self,
            )
            note.setObjectName("DocMeta")
            note.setWordWrap(True)
            column.addWidget(note)
            return

        column.addWidget(
            QLabel("Extracted values \u2014 tick what you confirm, edit if needed:", self)
        )
        self._rows: list[ConfirmRow] = []
        for proposal in draft.fields:
            row_widget = ConfirmRow(
                FIELD_LABELS.get(proposal.name, proposal.name),
                proposal.value,
                proposal.verified,
                proposal.rejected_reason,
                "document",
                self,
            )
            row_widget.field_name = proposal.name
            self._rows.append(row_widget)
            column.addWidget(row_widget)
        self._marked_unverified = sum(
            1 for proposal in draft.fields if not proposal.verified
        )
        if self._marked_unverified:
            warn = QLabel(
                f"{self._marked_unverified} value(s) do not appear word-for-word in "
                "the document \u2014 model guesses. Only tick them if you personally "
                "confirm they are right.",
                self,
            )
            warn.setObjectName("DocMeta")
            warn.setWordWrap(True)
            column.addWidget(warn)

        footer = QHBoxLayout()
        footer.addStretch(1)
        apply = QPushButton("Apply checked values to profile", self)
        apply.setObjectName("PrimaryButton")
        apply.clicked.connect(self._on_apply)
        footer.addWidget(apply)
        column.addLayout(footer)

    def document_id(self) -> int:
        return self._id

    def _on_apply(self) -> None:
        confirmed: dict[str, str | None] = {}
        for row_widget in self._rows:
            if row_widget.check.isChecked():
                value = row_widget.edit.text().strip()
                if value:
                    confirmed[row_widget.field_name] = value
        if not confirmed:
            QMessageBox.information(
                self,
                "Nothing ticked",
                "Tick at least one value to apply, then press Apply.",
            )
            return
        self.confirm_requested.emit(self._id, confirmed)


class DocumentsPage(QWidget):
    def __init__(
        self,
        database: Database,
        gateway: ModelGateway,
        model: str | None,
        on_profile_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._gateway = gateway
        self._model = model
        self._on_profile_changed = on_profile_changed
        self._worker: _IngestWorker | None = None
        self._current_document_id: int | None = None
        self._draft_for_reload: ProfileDraft | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        lead = QLabel(
            "Files stay on this machine. Text is read locally (or with Windows "
            "OCR) and sent to your model service only to propose values; you "
            "confirm each one before anything reaches your profile.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(lead)
        outer.addLayout(header)

        actions = QHBoxLayout()
        self.upload_button = QPushButton("Upload document\u2026", self)
        self.upload_button.setObjectName("PrimaryButton")
        self.upload_button.clicked.connect(self.choose_file)
        actions.addWidget(self.upload_button)
        self._status = QLabel("", self)
        self._status.setObjectName("PageLead")
        actions.addWidget(self._status, 1)
        outer.addLayout(actions)

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

        self._reload_cards()

    # -- uploads ------------------------------------------------------------
    def choose_file(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self, "Upload a document", "", SUPPORTED_FILES
        )
        if not chosen:
            return
        try:
            if Path(chosen).stat().st_size == 0:
                raise ValueError("The selected file is empty.")
        except OSError as exc:
            QMessageBox.warning(self, "Upload error", f"Cannot read that file: {exc}")
            return
        self._start_ingest(chosen)

    def _start_ingest(self, path: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Already working",
                "A document is still being processed. Please wait a moment.",
            )
            return
        self._status.setText("Reading the document\u2026")
        self.upload_button.setEnabled(False)
        self._worker = _IngestWorker(path, self._gateway, self._model)
        self._worker.parsed.connect(self._on_parsed)
        self._worker.proposed.connect(self._on_proposed)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _clear_worker(self) -> None:
        self._worker = None

    def _on_parsed(self, document: DocumentText | None, error: str) -> None:
        if error:
            self._status.setText("")
            QMessageBox.warning(self, "Could not read the file", error)
            self.upload_button.setEnabled(True)
            return
        if document is None:
            self._status.setText("")
            return
        document_id = self._database.add_document(
            filename=document.filename,
            mime=document.mime,
            text=document.text,
            ocr_used=document.ocr_used,
            warnings=document.warnings,
        )
        self._current_document_id = document_id
        if document.empty:
            QMessageBox.information(
                self,
                "No text found",
                document.warnings[0] if document.warnings
                else "No readable text was found in this document.",
            )
        self.upload_button.setEnabled(True)
        self._reload_cards(document_id=document_id)

    def _on_proposed(self, draft: ProfileDraft | None, error: str) -> None:
        self.upload_button.setEnabled(True)
        if error:
            self._status.setText("")
            QMessageBox.warning(
                self,
                "Extraction failed",
                f"{error}\n\nThe document text is saved; you can retry later.",
            )
            return
        if draft is None or not draft.fields:
            self._status.setText("Text saved. No extractable values were proposed.")
            return

        verified = sum(1 for field_value in draft.fields if field_value.verified)
        self._status.setText(
            f"{len(draft.fields)} value(s) proposed, {verified} verified against "
            "the document. Confirm what you trust, then Apply."
        )
        self._draft_for_reload = draft
        self._reload_cards(
            document_id=self._current_document_id, has_draft=True
        )

    # -- cards / persistence -------------------------------------------------
    def _reload_cards(
        self,
        document_id: int | None = None,
        has_draft: bool = False,
    ) -> None:
        while self._list.count() > 1:  # keep the trailing stretch
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # detach now; deleteLater alone stays painted
                widget.deleteLater()
        rows = list(self._database.documents())
        if not rows:
            placeholder = QLabel(
                "No documents yet. Upload a transcript, marksheet or "
                "language-test report to extract profile fields.",
                self,
            )
            placeholder.setObjectName("PageLead")
            self._list.insertWidget(0, placeholder)
        draft = self._draft_for_reload if has_draft and document_id is not None else None
        for row in rows:
            if draft is not None and row["id"] == document_id:
                self._database.save_extraction(document_id, {"proposed": [
                    {"name": field.name, "value": field.value,
                     "verified": field.verified}
                    for field in draft.fields
                ]})
            card = DocumentCard(
                row["id"],
                row["filename"],
                self._stored_document(row),
                draft if draft is not None and row["id"] == document_id else None,
            )
            card.confirm_requested.connect(self._on_confirm)
            card.deleted.connect(self._on_delete)
            self._list.insertWidget(self._list.count() - 1, card)

    def _stored_document(self, row: dict) -> DocumentText:
        return DocumentText(
            filename=row["filename"],
            mime=row["mime"],
            text=self._database.document_text(int(row["id"])),
            ocr_used=bool(row["ocr_used"]),
            warnings=list(row["warnings"]),
        )

    def _on_confirm(self, document_id: int, confirmed: dict[str, str | None]) -> None:
        """Merge the ticked values into the stored profile, never blindly."""
        record = self._database.load_profile()
        profile, _dropped = Profile.from_payload(record["data"] if record else {})
        merged = merge_confirmed(profile, confirmed)
        self._database.save_profile(merged.as_payload())
        self._database.save_extraction(
            document_id,
            {"applied": dict(confirmed)},
        )
        self._status.setText(
            f"Applied to your profile \u2014 {merged.completion()}% complete. "
            "Only the values you ticked were saved."
        )
        if self._on_profile_changed:
            self._on_profile_changed()

    def _on_delete(self, document_id: int) -> None:
        self._database.delete_document(document_id)
        logger.info("document %d deleted", document_id)
        self._reload_cards()

    def cancel_worker(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(2000)
