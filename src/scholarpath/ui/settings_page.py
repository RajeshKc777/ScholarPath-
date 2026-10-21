"""Settings page (M6): honest status of what this build uses and stores.

No switches it cannot honour: configuration is config.toml (validated, extra
keys rejected), so this page describes state and offers checks - it does not
pretend to edit the file. Gateway providers stay unnamed for students.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal, QUrl, Qt
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

from scholarpath.config import AppConfig, config_path
from scholarpath.mcp import McpError, probe_server

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
    def __init__(
        self,
        config: AppConfig,
        gateway_name: Callable[[], str],
        stats: Callable[[], dict],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._gateway_name = gateway_name
        self._stats = stats

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Settings", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "A plain description of what this build uses and stores. The one "
            "configuration file is config.toml - unknown keys and bad values "
            "are rejected, not ignored.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setObjectName("DocScroll")
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
        path = config_path()
        try:
            path_text = str(path)
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
        switches = self._config.privacy
        intro = QLabel(
            "All three are OFF by default. Nothing you type, say or search "
            "leaves this device until you turn one on in config.toml "
            "([privacy]). Here is exactly what each one sends, and to whom.",
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
            state = "ON" if enabled else "off"
            line = QLabel(
                f"{feature} — {state}. When on, {data} goes to {party}.",
                self,
            )
            line.setObjectName("StateWhat" if not enabled else "CardTitle")
            line.setWordWrap(True)
            privacy_layout.addWidget(line)
            key = QLabel(f"switch: privacy.{name} in config.toml", self)
            key.setObjectName("DocMeta")
            key.setWordWrap(True)
            privacy_layout.addWidget(key)

        always = QLabel(
            "Always local, never sent anywhere: your profile, your documents, "
            "the chat history, the saved opportunities and the logs.",
            self,
        )
        always.setObjectName("StateWhat")
        always.setWordWrap(True)
        privacy_layout.addWidget(always)
        open_config = QPushButton("Open config file", self)
        open_config.setObjectName("GhostButton")
        open_config.clicked.connect(self._open_config)
        privacy_layout.addWidget(open_config)

    def _open_folder(self) -> None:
        folder = config_path().parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_config(self) -> None:
        """Open the config file itself (or its folder when it does not exist)."""
        target = config_path()
        try:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    "[privacy]\nvoice_stt = false\nvoice_tts = false\n"
                    "web_search = false\n",
                    encoding="utf-8",
                )
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except OSError:
            self._open_folder()

    def shutdown(self) -> None:
        """Stop any running tool probes at window close."""
        for worker in self.findChildren(_ProbeWorker):
            worker.wait(2000)


def _add_at(column: QVBoxLayout, index: int, widget: QWidget) -> None:
    column.insertWidget(column.count() - 1, widget)
