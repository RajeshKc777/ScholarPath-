"""OpenCode adapter: session flow, error mapping and discovery against a fake server.

The fake mirrors the protocol verified against OpenCode 2.0.29:
service registration -> Basic auth -> create session -> prompt -> wait ->
read messages -> delete session. No real network beyond loopback.
"""

from __future__ import annotations

import base64
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import (
    ChatRequest,
    GatewayError,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
    Message,
)
from scholarpath.gateway.opencode import OpenCodeGateway, discover_service

PASSWORD = "test-password"


def _auth_header(password: str) -> str:
    raw = base64.b64encode(f"opencode:{password}".encode()).decode()
    return f"Basic {raw}"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _FakeServer:
    """Loopback OpenCode double with injectable failures."""

    def __init__(self) -> None:
        self.password = PASSWORD
        self.reply = "Model reply."
        self.assistant_available = True
        self.wait_delay = 0.0
        self.fail: dict | None = None  # {"code", "paths", "message"}
        self.corrupt_paths: tuple[str, ...] = ()
        self.models: list[dict] = [
            {
                "modelID": "m1-default",
                "providerID": "opencode",
                "name": "Default",
                "enabled": True,
                "capabilities": {"tools": False, "input": ["text"]},
                "limit": {"context": 32000},
                "cost": [{"input": 0.0, "output": 0.0}],
            },
            {
                "modelID": "m2-big",
                "providerID": "opencode",
                "name": "Big",
                "enabled": True,
                "capabilities": {"tools": True, "input": ["text"]},
                "limit": {"context": 128000},
                "cost": [{"input": 1.0, "output": 2.0}],
            },
        ]
        self.counters = {"create": 0, "prompt": 0, "wait": 0, "messages": 0, "delete": 0}
        self.received_prompts: list[str] = []
        self.received_models: list[dict] = []
        self.sessions: dict[str, str] = {}

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # silence test output
                pass

            def _fail_if_match(self) -> bool:
                fail = outer.fail
                if fail and any(p in self.path for p in fail["paths"]):
                    self._respond(fail["code"], {"message": fail["message"]})
                    return True
                return False

            def _respond(self, code: int, payload: dict | None = None) -> None:
                body = json.dumps(payload).encode() if payload is not None else b""
                self.send_response(code)
                if payload is not None:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _corrupt_if_match(self) -> bool:
                if any(p in self.path for p in outer.corrupt_paths):
                    raw = b'{"data": broken'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return True
                return False

            def _authorized(self) -> bool:
                if self.headers.get("Authorization") != _auth_header(outer.password):
                    self._respond(401, {"message": "unauthorized"})
                    return False
                return True

            def _session_id(self) -> str:
                return self.path.split("/")[3]

            def do_GET(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                if self.path == "/api/model":
                    self._respond(200, {"data": outer.models})
                    return
                if "/message" in self.path:
                    outer.counters["messages"] += 1
                    if self._corrupt_if_match():
                        return
                    session = outer.sessions.get(self._session_id(), "")
                    messages = [
                        {
                            "type": "user",
                            "id": "msg_u1",
                            "time": {"created": 1000},
                            "content": [{"type": "text", "text": session}],
                        }
                    ]
                    if outer.assistant_available:
                        messages.append(
                            {
                                "type": "assistant",
                                "id": "msg_a1",
                                "time": {"created": 2000},
                                "finish": "stop",
                                "content": [{"type": "text", "text": outer.reply}],
                                "tokens": {"input": 10, "output": 5},
                                "model": {
                                    "id": "m-served",
                                    "providerID": "opencode",
                                },
                            }
                        )
                    self._respond(200, {"data": messages})
                    return
                self._respond(404, {"message": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                if self._fail_if_match():
                    return
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""

                if self.path == "/api/session":
                    outer.counters["create"] += 1
                    outer.received_models.append(
                        json.loads(body or b"{}").get("model") or {}
                    )
                    session_id = f"ses_{outer.counters['create']:03d}"
                    outer.sessions[session_id] = ""
                    self._respond(200, {"data": {"id": session_id}})
                    return
                if "/prompt" in self.path:
                    outer.counters["prompt"] += 1
                    text = json.loads(body or b"{}").get("text", "")
                    outer.received_prompts.append(text)
                    outer.sessions[self._session_id()] = text
                    self._respond(
                        200,
                        {"data": {"id": f"msg_u{outer.counters['prompt']}", "time": {"created": 1000}}},
                    )
                    return
                if "/wait" in self.path:
                    outer.counters["wait"] += 1
                    if outer.wait_delay:
                        threading.Event().wait(outer.wait_delay)
                    self._respond(204)
                    return
                self._respond(404, {"message": "not found"})

            def do_DELETE(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                if self._fail_if_match():
                    return
                if self.path.startswith("/api/session/"):
                    outer.counters["delete"] += 1
                    outer.sessions.pop(self._session_id(), None)
                    self._respond(200, {"data": True})
                    return
                self._respond(404, {"message": "not found"})

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self._http.server_address[1])
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._http.shutdown()
        self._http.server_close()


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> _FakeServer:
    fake = _FakeServer()
    fake.start()
    monkeypatch.setenv("OPENCODE_SERVICE_PASSWORD", PASSWORD)
    yield fake
    fake.stop()


def _gateway(base_url: str, *, model: str = "", timeout: float = 3.0) -> OpenCodeGateway:
    return OpenCodeGateway(
        GatewayConfig(provider="opencode", base_url=base_url, model=model, timeout_seconds=timeout)
    )


def _chat(text: str = "hi") -> ChatRequest:
    return ChatRequest(messages=[Message(role="user", content=text)])


# -- happy path ------------------------------------------------------------------
def test_complete_round_trips_a_session(server: _FakeServer) -> None:
    server.reply = "Found nothing verified."
    gateway = _gateway(server.base_url)
    response = gateway.complete(_chat("Find scholarships"))

    assert response.text == "Found nothing verified."
    assert response.model == "opencode/m-served"
    assert response.finish_reason == "stop"
    assert response.usage == {"input": 10, "output": 5}
    assert server.counters["create"] == 1
    assert server.counters["prompt"] == 1
    assert server.counters["wait"] == 1
    assert server.counters["delete"] == 1


def test_prompt_carries_system_rules_and_history(server: _FakeServer) -> None:
    request = ChatRequest(
        messages=[
            Message(role="user", content="first"),
            Message(role="assistant", content="earlier reply"),
            Message(role="user", content="second"),
        ]
    )
    gateway = _gateway(server.base_url)
    gateway.complete(request)

    sent = server.received_prompts[0]
    assert "Never invent scholarships" in sent
    assert "User: first" in sent
    assert "Assistant: earlier reply" in sent
    assert "User: second" in sent
    assert sent.rstrip().endswith("Assistant:")


def test_request_level_model_overrides_config(server: _FakeServer) -> None:
    gateway = _gateway(server.base_url, model="opencode/m2-big")
    request = ChatRequest(messages=[Message(role="user", content="hi")], model="m-special")

    gateway.complete(request)

    # The request-level model is what reaches the server on session creation.
    assert server.received_models == [{"id": "m-special", "providerID": "opencode"}]


def test_registry_is_loaded_from_the_catalogue(server: _FakeServer) -> None:
    gateway = _gateway(server.base_url)
    entries = gateway.registry.all()

    # Two full entries prove the catalogue was loaded (config-only fallback
    # would leave an empty registry, and select would raise).
    assert [str(entry.ref) for entry in entries] == [
        "opencode/m1-default",
        "opencode/m2-big",
    ]
    assert entries[1].tools is True
    assert entries[1].context == 128000

    assert str(gateway.registry.select("chat")) == "opencode/m1-default"
    assert str(gateway.registry.select("research")) == "opencode/m2-big"


# -- discovery ---------------------------------------------------------------------
def test_discovery_reads_an_explicit_registration_file(
    server: _FakeServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENCODE_SERVICE_PASSWORD", raising=False)
    registration = tmp_path / "service.json"
    registration.write_text(
        json.dumps({"url": server.base_url, "password": PASSWORD}), encoding="utf-8"
    )

    endpoint = discover_service(str(registration))
    assert endpoint.url == server.base_url

    gateway = OpenCodeGateway(
        GatewayConfig(provider="opencode", service_file=str(registration), timeout_seconds=3.0)
    )
    response = gateway.complete(_chat("hi"))
    assert response.text == "Model reply."


# -- configuration errors ------------------------------------------------------------
def test_base_url_requires_the_password_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENCODE_SERVICE_PASSWORD", raising=False)
    with pytest.raises(GatewayNotConfigured) as excinfo:
        _gateway(f"http://127.0.0.1:{_free_port()}")
    assert "OPENCODE_SERVICE_PASSWORD" in str(excinfo.value)


def test_wrong_password_surfaces_as_not_configured(server: _FakeServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_SERVICE_PASSWORD", "incorrect")
    gateway = _gateway(server.base_url)
    with pytest.raises(GatewayNotConfigured):
        gateway.complete(_chat())


# -- error mapping --------------------------------------------------------------------
def _failing(code: int, message: str, monkeypatch: pytest.MonkeyPatch) -> tuple[_FakeServer, OpenCodeGateway]:
    fake = _FakeServer()
    fake.fail = {"code": code, "paths": ("/prompt",), "message": message}
    fake.start()
    monkeypatch.setenv("OPENCODE_SERVICE_PASSWORD", PASSWORD)
    return fake, _gateway(fake.base_url)


def test_rate_limit_maps_to_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, gateway = _failing(429, "slow down", monkeypatch)
    try:
        with pytest.raises(GatewayRateLimited):
            gateway.complete(_chat())
    finally:
        fake.stop()


def test_service_unavailable_maps_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, gateway = _failing(503, "provider down", monkeypatch)
    try:
        with pytest.raises(GatewayUnavailable) as excinfo:
            gateway.complete(_chat())
        assert "provider down" in str(excinfo.value)
    finally:
        fake.stop()


def test_unknown_endpoint_maps_to_protocol_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, gateway = _failing(404, "missing", monkeypatch)
    try:
        with pytest.raises(GatewayProtocolError):
            gateway.complete(_chat())
    finally:
        fake.stop()


def test_generic_http_error_maps_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, gateway = _failing(500, "boom", monkeypatch)
    try:
        with pytest.raises(GatewayUnavailable):
            gateway.complete(_chat())
    finally:
        fake.stop()


def test_unparseable_reply_is_a_protocol_error(server: _FakeServer) -> None:
    server.corrupt_paths = ("/message",)
    gateway = _gateway(server.base_url)
    with pytest.raises(GatewayProtocolError):
        gateway.complete(_chat())


def test_connection_refused_maps_to_unavailable(server: _FakeServer) -> None:
    gateway = _gateway(f"http://127.0.0.1:{_free_port()}", timeout=0.5)
    # The connect can surface as refused, or as a timeout on machines where the
    # kernel delays the refusal - both mean "cannot reach the service".
    with pytest.raises((GatewayUnavailable, GatewayTimeout)):
        gateway.complete(_chat())
    # the connection-refused test never reaches the fake server
    assert server.counters["create"] == 0


def test_wait_timeout_maps_to_timeout_error(server: _FakeServer) -> None:
    server.wait_delay = 1.5
    gateway = _gateway(server.base_url, timeout=0.4)
    with pytest.raises(GatewayTimeout):
        gateway.complete(_chat())


def test_missing_assistant_reply_times_out(server: _FakeServer) -> None:
    server.assistant_available = False
    gateway = _gateway(server.base_url, timeout=0.7)
    with pytest.raises(GatewayTimeout):
        gateway.complete(_chat())
