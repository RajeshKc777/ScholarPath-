"""MCP client over stdio: handshake, listing, calls, read-only guard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scholarpath.mcp import McpConnection, McpError, probe_server

FAKE_SERVER = str(Path(__file__).parent / "fake_mcp_server.py")


def connection() -> McpConnection:
    return McpConnection(sys.executable, [FAKE_SERVER], request_timeout=20.0)


def test_initialize_negotiates_and_lists_tools() -> None:
    conn = connection()
    try:
        version = conn.initialize()
        assert version == "2025-06-18"
        tools = {t.name: t for t in conn.list_tools()}
        assert set(tools) >= {"echo_text", "risky_write"}
        assert tools["echo_text"].read_only_hint is True
        assert tools["risky_write"].read_only_hint is False
    finally:
        conn.close()


def test_call_read_only_tool_returns_text() -> None:
    conn = connection()
    try:
        out = conn.call_tool("echo_text", {"text": "hello"}, read_only=True)
        assert out == 'echo: {"text": "hello"}'
    finally:
        conn.close()


def test_write_tool_blocked_in_read_only_mode() -> None:
    conn = connection()
    try:
        with pytest.raises(McpError) as error:
            conn.call_tool("risky_write", {"x": 1}, read_only=True)
        assert "read-only" in str(error.value)
        assert "blocked" in str(error.value)
    finally:
        conn.close()


def test_write_tool_allowed_when_read_only_disabled() -> None:
    conn = connection()
    try:
        # Not actually destructive: server marks it isError for non-echo calls,
        # which we surface as an McpError - the guard let the call through.
        with pytest.raises(McpError, match="execution error"):
            conn.call_tool("risky_write", {}, read_only=False)
    finally:
        conn.close()


def test_unknown_tool_is_refused_read_only() -> None:
    conn = connection()
    try:
        with pytest.raises(McpError, match="not offered"):
            conn.call_tool("ghost", {}, read_only=True)
    finally:
        conn.close()


def test_unannotated_tool_is_blocked_read_only() -> None:
    conn = connection()
    try:
        with pytest.raises(McpError, match="not marked read-only"):
            conn.call_tool("unannotated_tool", {}, read_only=True)
    finally:
        conn.close()


def test_missing_command_raises_friendly_error() -> None:
    conn = McpConnection("definitely_not_a_real_command_42", [], request_timeout=10)
    with pytest.raises(McpError, match="definitely_not_a_real_command_42"):
        conn.initialize()


def test_probe_server_returns_version_and_tools() -> None:
    version, tools = probe_server(sys.executable, [FAKE_SERVER])
    assert version == "2025-06-18"
    assert any(tool.name == "echo_text" for tool in tools)


def test_lazy_initialize_on_first_use() -> None:
    conn = connection()
    try:
        assert conn.server_version is None
        conn.list_tools()
        assert conn.server_version == "2025-06-18"
    finally:
        conn.close()


def test_close_is_idempotent() -> None:
    conn = connection()
    conn.initialize()
    conn.close()
    conn.close()
    with pytest.raises(McpError, match="closed"):
        conn.list_tools()
