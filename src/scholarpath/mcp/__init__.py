"""MCP client subpackage (G109). See `client.py` for the security rules."""

from scholarpath.mcp.client import (
    CALL_TIMEOUT_SECONDS,
    PROTOCOL_VERSION,
    McpConnection,
    McpError,
    Tool,
    probe_server,
)

__all__ = [
    "CALL_TIMEOUT_SECONDS",
    "PROTOCOL_VERSION",
    "McpConnection",
    "McpError",
    "Tool",
    "probe_server",
]
