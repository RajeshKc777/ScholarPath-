"""Settings page: privacy toggles, honest status, and local checks.

The three privacy switches are real: changing one updates the running app and
writes the value to ``config.toml`` without touching the rest of the file. The
other sections describe what the build uses and offer a read-only MCP check.
Gateway providers stay unnamed for students.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, QSignalBlocker, QSize, QThread, Signal, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from scholarpath.config import (
    AppConfig,
    ConfigError,
    config_path,
    save_privacy_config,
)
from scholarpath.mcp import McpError, probe_server
from scholarpath.ui import theme

logger = logging.getLogger("scholarpath.ui.settings")


class _Tool:
    __slots__ = ("name", "description", "read_only")

    def __init__(self, name: str, description: str, read_only: bool) -> None:
        self.name = name
        self.description = description
        self.read_only = read_only


class _ProbeWorker(QThread):
    """Initialize + tools/list for one enabled server, off the UI thread."""

    done = Signal(str, list, str)  # version, tools, error ("")

    def __init__(self, command: str, args: list[str], parent=None) -> None:
        super().__init__(parent)
        self._command = command
        self._args = args

    def run(self) -> None:
        try:
            version, tools = probe_server(self._command, self._args)
        except McpError as exc:
            logger.info("MCP probe failed for '%s': %s", self._command, exc)
            self.done.emit("", [], str(exc))
            return
        except Exception:  # noqa: BLE001 - unexpected errors surface plainly
            logger.exception("MCP probe crashed for '%s'", self._command)
            self.done.emit("", [], "The check failed unexpectedly.")
            return
        self.done.emit(
            version,
            [
                _Tool(t.name, t.description, t.read_only_hint)
                for t in tools
            ],
            "",
        )


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


class ToggleSwitch(QAbstractButton):
    """A small, keyboard-accessible on/off switch.

    Qt has no switch widget. A styled ``QCheckBox`` cannot draw a sliding knob,
    so this paints one; it still behaves like a button (Space clicks it, and
    Return/Enter does too).
    """

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.toggled.connect(self.update)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(46, 26)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        radius = rect.height() / 2
        track = QColor(
            theme.PALETTE["mint"] if self.isChecked() else theme.PALETTE["border_strong"]
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(rect, radius, radius)

        diameter = rect.height() - 6
        top = rect.top() + 3
        left = (
            rect.right() - diameter - 3
            if self.isChecked()
            else rect.left() + 3
        )
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(left, top, diameter, diameter))

        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(theme.PALETTE["orange"]), 1.5))
            painter.drawRoundedRect(rect.adjusted(-0.5, -0.5, 0.5, 0.5), radius, radius)


class PrivacySwitchRow(QFrame):
    """One privacy choice: feature name, disclosure, state and a real toggle."""

    toggled = Signal(str, bool)

    def __init__(
        self,
        name: str,
        feature: str,
        enabled: bool,
        party: str,
        data: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._feature = feature
        self.setObjectName("PrivacyRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(feature, self)
        title.setObjectName("CardTitle")
        detail = QLabel(f"When on, {data} goes to {party}.", self)
        detail.setObjectName("StateWhat")
        detail.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(detail)
        row.addLayout(text, 1)

        self._state = QLabel("", self)
        self._state.setFixedWidth(28)
        self._state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self._state, 0, Qt.AlignVCenter)

        self._toggle = ToggleSwitch(enabled, self)
        self._toggle.setObjectName("PrivacyToggle")
        self._toggle.setAccessibleName(feature)
        self._toggle.setAccessibleDescription(
            f"{feature}: when on, {data} goes to {party}."
        )
        self._toggle.toggled.connect(self._on_toggled)
        row.addWidget(self._toggle, 0, Qt.AlignVCenter)
        self._sync(enabled)

    @property
    def toggle(self) -> ToggleSwitch:
        return self._toggle

    def set_checked(self, checked: bool) -> None:
        blocker = QSignalBlocker(self._toggle)
        self._toggle.setChecked(checked)
        del blocker
        self._sync(checked)

    def _on_toggled(self, checked: bool) -> None:
        self._sync(checked)
        self.toggled.emit(self._name, checked)

    def _sync(self, checked: bool) -> None:
        self._state.setText("On" if checked else "Off")
        self._state.setObjectName("VerifyOK" if checked else "StateWhat")
        self._state.style().unpolish(self._state)
        self._state.style().polish(self._state)
        action = "off" if checked else "on"
        self._toggle.setToolTip(f"Turn {action} {self._feature}.")


class ServerRow(QFrame):
    """One configured MCP server: name, command, state, and a check button."""

    def __init__(self, server, read_only: bool, parent=None) -> None:
        super().__init__(parent)
        self._command = server.command
        self._args = server.args
        self._read_only = read_only
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 10, 14, 10)
        column.setSpacing(4)

        head = QHBoxLayout()
        name_label = QLabel(server.name, self)
        name_label.setObjectName("DocName")
        head.addWidget(name_label, 1)
        state = "Enabled in config" if server.enabled else "Off in config"
        chip = QLabel(state)
        chip.setObjectName("CapLive" if server.enabled else "CapSoon")
        head.addWidget(chip)
        column.addLayout(head)

        command_label = QLabel(f"command: {server.command} {' '.join(server.args)}", self)
        command_label.setObjectName("DocMeta")
        command_label.setWordWrap(True)
        column.addWidget(command_label)

        if not server.enabled:
            why = QLabel(
                "MCP servers never start on their own: flip "
                "enabled = true in config.toml first, then check tools here.",
                self,
            )
            why.setObjectName("StateWhat")
            why.setWordWrap(True)
            column.addWidget(why)
            self._check = None
        else:
            button_row = QHBoxLayout()
            self._check = QPushButton("Check tools", self)
            self._check.setObjectName("GhostButton")
            self._check.clicked.connect(self._start_probe)
            button_row.addWidget(self._check)
            self._status = QLabel("", self)
            self._status.setObjectName("DocMeta")
            self._status.setWordWrap(True)
            button_row.addWidget(self._status, 1)
            column.addLayout(button_row)

    def _start_probe(self) -> None:
        if self._check is None:
            return
        self._check.setEnabled(False)
        self._status.setText("Starting the server to list tools…")
        self._worker = _ProbeWorker(self._command, self._args, self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, version: str, tools: list[_Tool], error: str) -> None:
        if self._check is not None:
            self._check.setEnabled(True)
        if error:
            self._status.setText(f"Failed: {_short(error, 160)}")
            return
        lines = [f"Connected \u2014 protocol {version}, {len(tools)} tool(s):"]
        for tool in tools:
            marker = "read-only" if tool.read_only else "not read-only"
            lines.append(f"  \u2022 {tool.name} ({marker}): {_short(tool.description or 'no description', 70)}")
        lines.append(
            "Read-only tools only run while config keeps "
            "read_only = true. Tool output is data, never instructions."
        )
        self._status.setText("\n".join(lines))


class SettingsPage(QWidget):
    privacy_changed = Signal()

    def __init__(
        self,
        config: AppConfig,
        gateway_name: Callable[[], str],
        stats: Callable[[], dict],
        parent: QWidget | None = None,
        config_file: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._gateway_name = gateway_name
        self._stats = stats
        self._config_file = config_file or config_path()
        self._privacy_rows: dict[str, PrivacySwitchRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Settings", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "Privacy switches save automatically. Advanced settings live in "
            "config.toml, where unknown keys and bad values are rejected, not "
            "ignored.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setObjectName("DocScroll")
        self._scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setObjectName("DocBody")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 12)
        column.setSpacing(12)
        column.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        def card(name: str) -> QVBoxLayout:
            frame = QFrame(holder)
            frame.setObjectName("PanelCard")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(6)
            _add_at(column, -1, frame)
            heading = QLabel(name, frame)
            heading.setObjectName("CardTitle")
            layout.addWidget(heading)
            return layout

        # -- model replies --------------------------------------------------
        model_layout = card("Model replies")
        live = self._gateway_name() != "stub"
        state = QLabel(
            "Live - replies run through the local model service. That service "
            "must be running separately; no student-visible provider names "
            "exist in this interface."
            if live
            else "Offline preview - replies are placeholder text with no model "
            "behind them.",
            self,
        )
        state.setObjectName("StateWhy")
        state.setWordWrap(True)
        model_layout.addWidget(state)

        # -- local data -----------------------------------------------------
        data_layout = card("Local data")
        try:
            path_text = str(self._config_file)
        except Exception:  # noqa: BLE001 - config path is only display
            path_text = "(not resolvable)"
        file_label = QLabel(f"config file: {path_text}", self)
        file_label.setObjectName("DocMeta")
        file_label.setWordWrap(True)
        data_layout.addWidget(file_label)
        counts = self._stats()
        summary = QLabel(
            f"documents: {counts.get('documents', 0)}  \u00b7  "
            f"verified scholarship records: {counts.get('scholarships', 0)}  \u00b7  "
            f"saved opportunities: {counts.get('saved', 0)}",
            self,
        )
        summary.setObjectName("StateWhy")
        summary.setWordWrap(True)
        data_layout.addWidget(summary)
        open_folder = QPushButton("Open config folder", self)
        open_folder.setObjectName("GhostButton")
        open_folder.clicked.connect(self._open_folder)
        data_layout.addWidget(open_folder)
        privacy = QLabel(
            "Documents stay on this device; only extracted text travels to the "
            "model service, and only to propose values you must confirm.",
            self,
        )
        privacy.setObjectName("StateWhat")
        privacy.setWordWrap(True)
        data_layout.addWidget(privacy)
        # -- tools (MCP) -----------------------------------------------------
        tools_layout = card("Tools (MCP)")
        mcp = self._config.mcp
        mcp_state = QLabel(
            (
                f"How this works: MCP is wired in but entirely opt-in. It is "
                f"{'on' if mcp.enabled else 'off'} in config "
                f"(read_only: {'yes' if mcp.read_only else 'no'}), with "
                f"{len(mcp.servers)} server(s) configured. No server starts "
                "until both the app-level switch and its own "
                "enabled = true are set."
            ),
            self,
        )
        mcp_state.setObjectName("StateWhy")
        mcp_state.setWordWrap(True)
        tools_layout.addWidget(mcp_state)
        if not mcp.servers:
            empty = QLabel(
                "No servers configured. To add one, append an "
                "[[mcp.servers]] block with name, command and args to "
                "config.toml.",
                self,
            )
            empty.setObjectName("StateWhat")
            empty.setWordWrap(True)
            tools_layout.addWidget(empty)
        for server in mcp.servers:
            tools_layout.addWidget(ServerRow(server, mcp.read_only, holder))

        # -- privacy: what may leave this device ------------------------------
        privacy_layout = card("Privacy: what may leave this device")
        self._privacy_card = privacy_layout.parentWidget()
        switches = self._config.privacy
        intro = QLabel(
            "These switches decide what may leave this device. They start ON "
            "so voice and web search work without editing a file. Every change "
            "saves automatically; turn off anything you do not want to share. "
            "Here is exactly what each one sends, and to whom.",
            self,
        )
        intro.setObjectName("StateWhy")
        intro.setWordWrap(True)
        privacy_layout.addWidget(intro)

        disclosures = (
            (
                "voice_stt",
                switches.voice_stt,
                "Voice input (speech to text)",
                "Google's speech service",
                "a short microphone clip of your voice, which is transcribed "
                "into text",
            ),
            (
                "voice_tts",
                switches.voice_tts,
                "Spoken replies (text to speech)",
                "Microsoft's speech service",
                "the text of the reply, which is turned into audio and played "
                "on this device",
            ),
            (
                "web_search",
                switches.web_search,
                "Web search in the chat",
                "the web-search service (DuckDuckGo)",
                "the search question, and the pages it returns, which are "
                "fetched and shown to the model",
            ),
        )
        for name, enabled, feature, party, data in disclosures:
            row = PrivacySwitchRow(name, feature, enabled, party, data, self)
            row.toggled.connect(self._on_privacy_toggled)
            privacy_layout.addWidget(row)
            self._privacy_rows[name] = row

        self._privacy_saved = QLabel("", self)
        self._privacy_saved.setObjectName("DocMeta")
        self._privacy_saved.setWordWrap(True)
        privacy_layout.addWidget(self._privacy_saved)

        always = QLabel(
            "Always local, never sent anywhere: your profile, your documents, "
            "the chat history, the saved opportunities and the logs.",
            self,
        )
        always.setObjectName("StateWhat")
        always.setWordWrap(True)
        privacy_layout.addWidget(always)
        reminders_note = QLabel(
            "The deadline reminder is a notification Windows draws on this "
            "device. No third party receives anything, and it is off until "
            "you turn it on.",
            self,
        )
        reminders_note.setObjectName("StateWhat")
        reminders_note.setWordWrap(True)
        privacy_layout.addWidget(reminders_note)

        # -- freshness and reminders (Phase 3) ------------------------------
        fresh_layout = card("Freshness and reminders")
        freshness = self._config.freshness
        reminders = self._config.reminders
        fresh_state = QLabel(
            f"Background re-check: {'on' if freshness.auto else 'off'}. "
            f"A record is checked again when its last check is more than "
            f"{freshness.interval_hours} hour(s) old, and one run reads at "
            f"most {freshness.max_per_run} record(s). The saved records are "
            "always checked first. A page that changed is read again and "
            "verified word-for-word against the new page text; the older "
            "version is kept.",
            self,
        )
        fresh_state.setObjectName("StateWhy")
        fresh_state.setWordWrap(True)
        fresh_layout.addWidget(fresh_state)
        fresh_key = QLabel("switch: freshness.auto in config.toml", self)
        fresh_key.setObjectName("DocMeta")
        fresh_key.setWordWrap(True)
        fresh_layout.addWidget(fresh_key)

        reminder_switch = "on" if reminders.enabled else "off (the default)"
        reminder_state = QLabel(
            f"Deadline reminders: {reminder_switch}. When on, Windows shows a "
            "local notification at 30, 14, 7 and 1 days before the deadline "
            "of a saved record. Only a record with a clear deadline date is "
            "reminded about, and the same reminder is not shown twice on "
            "one day.",
            self,
        )
        reminder_state.setObjectName("StateWhy")
        reminder_state.setWordWrap(True)
        fresh_layout.addWidget(reminder_state)
        reminder_key = QLabel("switch: reminders.enabled in config.toml", self)
        reminder_key.setObjectName("DocMeta")
        reminder_key.setWordWrap(True)
        fresh_layout.addWidget(reminder_key)

    def focus_privacy(self) -> None:
        """Scroll the privacy card into view (a gated voice control sends us here)."""
        card = getattr(self, "_privacy_card", None)
        if card is None:
            return
        self._scroll.ensureWidgetVisible(card)
        first = self._privacy_rows.get("voice_stt")
        if first is not None:
            first.toggle.setFocus()

    def _on_privacy_toggled(self, name: str, enabled: bool) -> None:
        """Apply the switch at once, then save only if the write succeeds."""
        row = self._privacy_rows.get(name)
        if row is None:
            return
        previous = bool(getattr(self._config.privacy, name))
        if previous == enabled:
            return
        setattr(self._config.privacy, name, enabled)
        try:
            save_privacy_config(self._config.privacy, self._config_file)
        except Exception as exc:  # noqa: BLE001 - a failed write must never lie
            setattr(self._config.privacy, name, previous)
            row.set_checked(previous)
            logger.warning("privacy switch %s could not be saved: %s", name, exc)
            self._set_privacy_message(
                f"Could not save that change: {_short(str(exc), 160)}", ok=False
            )
            return
        logger.info("privacy switch %s set to %s", name, enabled)
        self._set_privacy_message("Saved. This choice is remembered.", ok=True)
        self.privacy_changed.emit()

    def _set_privacy_message(self, text: str, ok: bool) -> None:
        self._privacy_saved.setText(text)
        self._privacy_saved.setObjectName("VerifyOK" if ok else "VerifyWarn")
        self._privacy_saved.style().unpolish(self._privacy_saved)
        self._privacy_saved.style().polish(self._privacy_saved)

    def _open_folder(self) -> None:
        folder = self._config_file.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def shutdown(self) -> None:
        """Stop any running tool probes at window close."""
        for worker in self.findChildren(_ProbeWorker):
            worker.wait(2000)


def _add_at(column: QVBoxLayout, index: int, widget: QWidget) -> None:
    column.insertWidget(column.count() - 1, widget)
