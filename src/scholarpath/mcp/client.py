"""Minimal MCP client over stdio (JSON-RPC 2.0, newline-delimited).

Implements exactly the subset this build needs: `initialize`, `tools/list`,
`tools/call`. No SDK dependency (G112): the official SDK would drag in a large
async transport stack for a byte pipe.

Security rules (G109):
- A server only starts when its config entry is `enabled`.
- Tool results are untrusted data: per-message size cap, malformed lines are
  dropped (counted), nothing is ever executed from server output.
- With `read_only = true` (the default), `tools/call` refuses any tool whose
  advertised annotations do not assert `readOnlyHint: true`.
- Everything on stderr from the server is ignored (never quoted into logs
  verbatim); only counters go to our structured log.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading

logger = logging.getLogger("scholarpath.mcp")

PROTOCOL_VERSION = "2025-06-18"
MAX_MESSAGE_BYTES = 1_000_000  # per inbound message; bigger lines are refused
CALL_TIMEOUT_SECONDS = 60.0


class McpError(Exception):
    """Any MCP transport or protocol failure (details are safe to show)."""


class Tool:
    """A tool advertised by a server. Data only."""

    __slots__ = ("name", "description", "read_only_hint")

    def __init__(self, name: str, description: str, read_only_hint: bool) -> None:
        self.name = name
        self.description = description
        self.read_only_hint = read_only_hint


class McpConnection:
    """One child process speaking MCP over stdio.

    Spawned lazily; wire-level calls are serialised by a lock; every call has
    a timeout so a wedged server cannot freeze the app (the process is killed
    on timeout and the caller reports an error).
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        request_timeout: float = 30.0,
    ) -> None:
        self._command = command
        self._args = list(args or [])
        self._request_timeout = request_timeout
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_id = 1
        self.server_version: str | None = None
        self._dead = False

    # -- process lifecycle -------------------------------------------------

    def _spawn(self) -> None:
        if self._process is not None:
            return
        try:
            self._process = subprocess.Popen(
                [self._command, *self._args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # server logs must never enter ours
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise McpError(f"Cannot start MCP server '{self._command}': {exc}") from exc

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.stdin is not None:
                self._process.stdin.close()
        except OSError:
            pass
        try:
            self._process.terminate()
        except OSError:
            pass
        try:
            self._process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            self._process.kill()
        self._process = None
        self._dead = True

    # -- low level ---------------------------------------------------------

    def _send(self, payload: dict) -> None:
        assert self._process is not None and self._process.stdin is not None
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            self._process.stdin.write(line + "\n")
            self._process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise McpError(f"MCP server pipe is broken: {exc}") from exc

    def _read_response(self, request_id: int, timeout: float) -> dict:
        """Read lines until the response for `request_id` arrives.

        Notifications are skipped; malformed/oversized lines raise so a
        misbehaving server cannot stall the caller silently.
        """
        assert self._process is not None and self._process.stdout is not None
        rejected = 0
        while True:
            line = self._process.stdout.readline()
            if not line:
                self._dead = True
                raise McpError("MCP server closed the connection")
            line = line.strip()
            if not line:
                continue
            if len(line.encode("utf-8", errors="replace")) > MAX_MESSAGE_BYTES:
                self.close()
                raise McpError("MCP server sent an oversized message; disconnected")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                rejected += 1
                if rejected > 16:
                    self.close()
                    raise McpError("MCP server sent too many non-JSON lines")
                continue
            if not isinstance(message, dict):
                rejected += 1
                continue
            if message.get("id") != request_id:
                continue  # notification or unrelated message: untrusted, skipped
            error = message.get("error")
            if error is not None:
                detail = error.get("message", "unknown error") if isinstance(
                    error, dict
                ) else str(error)
                raise McpError(f"MCP error: {detail}")
            return message.get("result") or {}

    def _request(self, method: str, params: dict, timeout: float | None = None) -> dict:
        if self._dead:
            raise McpError("MCP connection is closed")
        with self._lock:
            self._spawn()
            request_id = self._next_id
            self._next_id += 1
            self._send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            try:
                return self._read_response(
                    request_id, timeout or self._request_timeout
                )
            except McpError:
                if method == "initialize" or self._dead:
                    self.close()
                raise

    # -- protocol ----------------------------------------------------------

    def initialize(self) -> str:
        """Complete the MCP handshake; returns the negotiated protocol version."""
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "ScholarPath", "version": "0.5.0"},
            },
        )
        version = str(result.get("protocolVersion") or PROTOCOL_VERSION)
        self.server_version = version
        # The initialized notification expects no response.
        with self._lock:
            if self._process is not None:
                try:
                    self._send(
                        {"jsonrpc": "2.0", "method": "notifications/initialized"}
                    )
                except McpError:
                    pass
        return version

    def _ensure_ready(self) -> None:
        if self.server_version is None:
            self.initialize()

    def list_tools(self) -> list[Tool]:
        """Advertised tools; annotations decide the read-only hint (default: no)."""
        self._ensure_ready()
        result = self._request("tools/list", {})
        tools: list[Tool] = []
        for item in result.get("tools", []) or []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue  # malformed entry: dropped, not trusted
            annotations = item.get("annotations") or {}
            hint = annotations.get("readOnlyHint") is True
            tools.append(
                Tool(
                    name=item["name"],
                    description=str(item.get("description") or ""),
                    read_only_hint=hint,
                )
            )
        return tools

    def call_tool(
        self, name: str, arguments: dict | None, read_only: bool
    ) -> str:
        """Call a tool. `read_only` mirrors config: when true, only tools that
        advertise `readOnlyHint: true` may run. Returns the text blocks joined."""
        self._ensure_ready()
        if read_only:
            advertised = {tool.name: tool for tool in self.list_tools()}
            tool = advertised.get(name)
            if tool is None:
                raise McpError(f"Tool '{name}' is not offered by this server")
            if not tool.read_only_hint:
                raise McpError(
                    f"Tool '{name}' is not marked read-only; blocked by config"
                )
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            timeout=CALL_TIMEOUT_SECONDS,
        )
        if result.get("isError"):
            raise McpError("Tool reported an execution error")
        texts: list[str] = []
        for block in result.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if len(text.encode("utf-8", errors="replace")) > MAX_MESSAGE_BYTES:
                    raise McpError("Tool returned an oversized result")
                texts.append(str(text))
        return "\n".join(texts)


# -- config-facing surface -----------------------------------------------------


def probe_server(
    command: str, args: list[str], timeout: float = 20.0
) -> tuple[str, list[Tool]]:
    """Start, initialize, list tools, and close. Used by the Settings page."""
    connection = McpConnection(command, args, request_timeout=timeout)
    try:
        version = connection.initialize()
        tools = connection.list_tools()
        return version, tools
    except McpError:
        connection.close()
        raise
    finally:
        connection.close()
