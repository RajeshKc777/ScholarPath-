"""Main window: chat shell for Milestone 1.

Deliberately small. Result cards, filters, profiles, and comparison arrive in
later milestones; this window proves the conversation loop and error surfaces.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from scholarpath.config import AppConfig, config_path
from scholarpath.ui.chat_controller import ChatController, Turn

_STYLE = """
QWidget { background: #12151c; color: #e6e9f0; font-family: 'Segoe UI', sans-serif; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#subtitle { color: #8b93a7; font-size: 12px; }
QLabel#status { color: #8b93a7; font-size: 11px; }
QTextBrowser {
    background: #191d26; border: 1px solid #242a36; border-radius: 10px; padding: 12px;
}
QPlainTextEdit {
    background: #191d26; border: 1px solid #2c3442; border-radius: 10px;
    padding: 10px; font-size: 13px; selection-background-color: #4f8cff;
}
QPlainTextEdit:focus { border: 1px solid #4f8cff; }
QPushButton {
    background: #4f8cff; color: #0b1020; border: none; border-radius: 10px;
    padding: 11px 22px; font-weight: 600; font-size: 13px;
}
QPushButton:disabled { background: #2c3442; color: #6b7280; }
QPushButton:hover:!disabled { background: #6ba0ff; }
"""


class ChatInput(QPlainTextEdit):
    """Enter sends, Shift+Enter inserts a newline."""

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        is_enter = event.key() in (Qt.Key_Return, Qt.Key_Enter)
        if is_enter and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(
        self,
        controller: ChatController,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._config = config
        self._error_text: str | None = None
        self._blocks: list[str] = []

        self.setWindowTitle("ScholarPath AI")
        self.resize(config.ui.window_width, config.ui.window_height)
        self.setStyleSheet(_STYLE)

        self._build_ui()
        self._connect()
        self._render_welcome()

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QLabel("ScholarPath AI")
        title.setObjectName("title")
        subtitle = QLabel(
            "Scholarship discovery and academic guidance \u00b7 offline build (Milestone 1)"
        )
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.transcript = QTextBrowser(root)
        self.transcript.setOpenExternalLinks(True)
        layout.addWidget(self.transcript, 1)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.input = ChatInput(root)
        self.input.setPlaceholderText(
            "Describe your study plans, or say hello \u2014 Enter to send, Shift+Enter for a new line"
        )
        self.input.setFixedHeight(84)
        self.send_button = QPushButton("Send", root)
        self.send_button.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_button, 0, Qt.AlignBottom)
        layout.addLayout(row)

        self.status = QLabel(root)
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.setCentralWidget(root)
        self._refresh_status()

    def _connect(self) -> None:
        self.send_button.clicked.connect(self._submit)
        self.input.submitted.connect(self._submit)
        self._controller.turn_added.connect(self._on_turn_added)
        self._controller.busy_changed.connect(self._on_busy_changed)
        self._controller.failed.connect(self._on_failed)

    # -- behaviour --------------------------------------------------------
    def _submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self._controller.send(text):
            self.input.clear()

    def _on_turn_added(self, turn: Turn) -> None:
        self._blocks.append(self._render_turn(turn))
        self._refresh_transcript()
        self._refresh_status()

    def _on_busy_changed(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.send_button.setText("Working\u2026" if busy else "Send")
        if busy:
            self._error_text = None
        self._refresh_status(busy=busy)

    def _on_failed(self, message: str) -> None:
        self._error_text = message
        self._refresh_status()

    # -- rendering --------------------------------------------------------
    def _render_welcome(self) -> None:
        location = html.escape(str(config_path()))
        self._blocks.append(
            "<p style='margin:0 0 6px 0; color:#e6e9f0; font-size:14px;'>"
            "<b>What this build does</b></p>"
            "<p style='margin:0 0 10px 0; color:#8b93a7; font-size:12px;'>"
            "Chat is wired end to end against an <b>offline stub model</b>. No network, "
            "no scholarships, no eligibility checks yet \u2014 those come in later milestones."
            "</p>"
            f"<p style='margin:0 0 2px 0; color:#8b93a7; font-size:12px;'>"
            f"Configuration: <code>{location}</code></p>"
            "<p style='margin:0 0 4px 0; color:#8b93a7; font-size:12px;'>"
            "Create it with <code>scholarpath --init-config</code>.</p>"
        )
        self._refresh_transcript()

    def _refresh_transcript(self) -> None:
        """Re-render the whole document so blocks never collapse into one line."""
        self.transcript.setHtml("".join(self._blocks))
        self.transcript.moveCursor(QTextCursor.End)
        self.transcript.ensureCursorVisible()

    @staticmethod
    def _render_turn(turn: Turn) -> str:
        is_user = turn.role == "user"
        speaker = "YOU" if is_user else "SCHOLARPATH"
        model = turn.model or None
        if model and not is_user:
            speaker += f" \u00b7 {html.escape(model)}"

        colour = "#9fb4d8" if is_user else ("#ff9f9f" if turn.error else "#e6e9f0")
        body = html.escape(turn.text).replace("\n", "<br>")
        return (
            "<p style='margin:16px 0 2px 0; color:#8b93a7; font-size:10px; "
            f"letter-spacing:1px;'>{speaker}</p>"
            f"<p style='margin:0 0 10px 0; color:{colour}; font-size:13px;'>{body}</p>"
        )

    def _refresh_status(self, busy: bool | None = None) -> None:
        if busy is None:
            busy = self._controller.busy

        if self._error_text is not None and not busy:
            self.status.setText(f"Error \u2014 {self._error_text}")
            self.status.setStyleSheet("color: #ff8f8f;")
            return

        model = self._controller.model or "default"
        state = "Thinking\u2026" if busy else "Ready"
        self.status.setText(
            f"{state} \u00b7 gateway: {self._controller.gateway_name} \u00b7 model: {model} "
            "\u00b7 no research is performed in this build"
        )
        self.status.setStyleSheet("color: #8b93a7;")
