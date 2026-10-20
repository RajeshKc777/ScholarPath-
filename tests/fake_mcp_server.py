"""A minimal MCP server for tests: speaks JSON-RPC over stdio lines.

Advertises two tools:
- `echo_text`   - annotations.readOnlyHint = true
- `risky_write` - annotations.readOnlyHint = false

`tools/call echo_text` returns the arguments echoed as text, then exits.
"""

import json
import sys

PROTOCOL_VERSION = "2025-06-18"


def respond(message: dict, result: dict) -> None:
    sys.stdout.write(
        json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}) + "\n"
    )
    sys.stdout.flush()


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = message.get("method")

        if method == "initialize":
            respond(
                message,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake", "version": "1.0.0"},
                },
            )
        elif method == "tools/list":
            respond(
                message,
                {
                    "tools": [
                        {
                            "name": "echo_text",
                            "description": "Echo the given text back.",
                            "annotations": {"readOnlyHint": True},
                        },
                        {
                            "name": "risky_write",
                            "description": "Pretends to modify something.",
                            "annotations": {"readOnlyHint": False},
                        },
                        {
                            "name": "unannotated_tool",  # no annotations: hint absent
                        },
                    ]
                },
            )
        elif method == "tools/call":
            name = message.get("params", {}).get("name")
            if name == "echo_text":
                args = message.get("params", {}).get("arguments", {})
                respond(
                    message,
                    {
                        "content": [
                            {"type": "text", "text": "echo: %s" % json.dumps(args)}
                        ],
                        "isError": False,
                    },
                )
            else:
                respond(
                    message,
                    {"content": [], "isError": True},
                )
        elif method == "ping":
            respond(message, {})


if __name__ == "__main__":
    main()
