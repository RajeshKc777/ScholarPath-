"""Chat → profile suggestion card (G117): propose, confirm per field, merge.

The card is inserted into the chat transcript right after the assistant's
reply when the student's message contained verifiable profile facts. Only the
rows the student keeps ticked are saved; values stay editable; nothing is
ever saved without that explicit confirmation.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from scholarpath.chat_profile import (
    CHAT_PROFILE_FIELDS,
    _CHAT_FIELD_LABELS,
    build_profile_update_prompt,
    parse_profile_updates,
)
from scholarpath.gateway.base import ChatRequest, GatewayError, Message, ModelGateway
from scholarpath.ui.confirm_row import ConfirmRow

logger = logging.getLogger("scholarpath.ui.chat_profile")


class _ProfileScanWorker(QThread):
    """Background extraction: does the latest user message state profile facts?"""

    scanned = Signal(object, str)  # dict | None, error ("")

    def __init__(
        self, message: str, gateway: ModelGateway, model: str | None
    ) -> None:
        super().__init__()
        self._message = message
        self._gateway = gateway
        self._model = model

    def run(self) -> None:
        request = ChatRequest(
            messages=[
                Message(role="user", content=build_profile_update_prompt(self._message))
            ],
            model=self._model,
        )
        try:
            response = self._gateway.complete(request)
        except GatewayError as exc:
            logger.info("profile scan skipped: %s", exc.message)
            self.scanned.emit(None, "")
            return
        except Exception:  # noqa: BLE001 - suggestions must never break chat
            logger.exception("profile scan crashed")
            self.scanned.emit(None, "")
            return
        try:
            updates = parse_profile_updates(response.text, self._message)
        except Exception:  # noqa: BLE001 - unparsable reply = no suggestion
            logger.info("profile scan reply was not usable JSON")
            self.scanned.emit(None, "")
            return
        self.scanned.emit(updates or None, "")


class ProfileSuggestionCard(QFrame):
    """Confirmation card: one row per proposed field, all editable."""

    def __init__(
        self,
        updates: dict[str, str],
        on_save: Callable[[dict[str, str]], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_save_callback = on_save
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)

        title = QLabel("From your message \u2014 save these to your profile?", self)
        title.setObjectName("DocName")
        column.addWidget(title)
        lead = QLabel(
            "Tick each value you want saved (you can edit before saving). "
            "Saved once, reused everywhere \u2014 no need to re-enter or "
            "re-upload these details later. Nothing is saved without your tick.",
            self,
        )
        lead.setObjectName("StateWhy")
        lead.setWordWrap(True)
        column.addWidget(lead)

        self._rows: dict[str, ConfirmRow] = {}
        for name in CHAT_PROFILE_FIELDS:
            if name not in updates:
                continue
            label = _CHAT_FIELD_LABELS.get(name, name)
            row = ConfirmRow(
                label, updates[name], verified=True, source_noun="your message", parent=self
            )
            self._rows[name] = row
            column.addWidget(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        dismiss = QPushButton("Not now", self)
        dismiss.setObjectName("GhostButton")
        dismiss.clicked.connect(self.deleteLater)
        buttons.addWidget(dismiss)
        save = QPushButton("Save to profile", self)
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._on_save)
        buttons.addWidget(save)
        column.addLayout(buttons)

    def _on_save(self) -> None:
        selected = {
            name: row.edit.text().strip()
            for name, row in self._rows.items()
            if row.check.isChecked() and row.edit.text().strip()
        }
        callback = self._on_save_callback
        self.deleteLater()
        if selected:
            callback(selected)
