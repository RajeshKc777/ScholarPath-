"""Failover behaviour of the OpenCode adapter.

Covers the case the app was built for: a model that answers "Rate limit
exceeded" must not end the turn. The fake service can

- refuse specific models with a quota error,
- refuse specific accounts (credential) with a quota error,
- hold a store of accounts the app may switch between.

No network beyond loopback.
"""

from __future__ import annotations

import base64
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import ChatRequest, GatewayRateLimited, Message
from scholarpath.gateway.opencode import OpenCodeGateway

PASSWORD = "test-password"


def _auth_header(password: str) -> str:
    raw = base64.b64encode(f"opencode:{password}".encode()).decode()
    return f"Basic {raw}"


class _FakeService:
    """Loopback OpenCode double with per-model and per-account failures."""

    def __init__(self) -> None:
        self.password = PASSWORD
        self.reply = "Model reply."
        self.quota_models: set[str] = set()
        self.quota_accounts: set[str] = set()
        self.credentials: list[dict] = []
        self.models: list[dict] = [
            {
                "modelID": "deepseek-v4.1-flash-free",
                "providerID": "opencode",
                "name": "DeepSeek",
                "enabled": True,
                "capabilities": {"tools": False, "input": ["text"]},
                "limit": {"context": 32000},
                "cost": [{"input": 0.0, "output": 0.0}],
            },
            {
                "modelID": "beam-free",
                "providerID": "opencode",
                "name": "Beam",
                "enabled": True,
                "capabilities": {"tools": False, "input": ["text"]},
                "limit": {"context": 32000},
                "cost": [{"input": 0.0, "output": 0.0}],
            },
        ]
        self.received_models: list[str] = []
        self.activated: list[str] = []
        self.registered: list[dict] = []
        self.active_credential: str | None = None
        self.session_model: dict[str, str] = {}
        self._counter = 0

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _respond(self, code: int, payload: dict | None = None) -> None:
                body = json.dumps(payload).encode() if payload is not None else b""
                self.send_response(code)
                if payload is not None:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _authorized(self) -> bool:
                if self.headers.get("Authorization") != _auth_header(outer.password):
                    self._respond(401, {"message": "unauthorized"})
                    return False
                return True

            def _session_id(self) -> str:
                return self.path.split("/")[3]

            def _quota(self, model: str) -> bool:
                if model in outer.quota_models:
                    return True
                account = outer.active_credential
                return bool(account and account in outer.quota_accounts)

            def do_GET(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                if self.path == "/api/model":
                    self._respond(200, {"data": outer.models})
                    return
                if self.path == "/api/credential":
                    self._respond(200, {"data": outer.credentials})
                    return
                if "/message" in self.path:
                    model = outer.session_model.get(self._session_id(), "")
                    if self._quota(model):
                        self._respond(
                            200,
                            {
                                "data": [
                                    {
                                        "type": "assistant",
                                        "id": "msg_a1",
                                        "time": {"created": 2000},
                                        "finish": "error",
                                        "content": [],
                                        "error": {
                                            "type": "provider.quota",
                                            "message": "Rate limit exceeded. Please try again later.",
                                        },
                                        "model": {"id": model, "providerID": "opencode"},
                                    }
                                ]
                            },
                        )
                        return
                    self._respond(
                        200,
                        {
                            "data": [
                                {
                                    "type": "assistant",
                                    "id": "msg_a1",
                                    "time": {"created": 2000},
                                    "finish": "stop",
                                    "content": [{"type": "text", "text": outer.reply}],
                                    "tokens": {"input": 10, "output": 5},
                                    "model": {"id": model, "providerID": "opencode"},
                                }
                            ]
                        },
                    )
                    return
                self._respond(404, {"message": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b"{}"

                if self.path == "/api/session":
                    outer._counter += 1
                    session_id = f"ses_{outer._counter:03d}"
                    model = (json.loads(body).get("model") or {}).get("id", "")
                    outer.session_model[session_id] = model
                    outer.received_models.append(model)
                    self._respond(200, {"data": {"id": session_id}})
                    return
                if "/prompt" in self.path:
                    self._respond(
                        200,
                        {"data": {"id": "msg_u1", "time": {"created": 1000}}},
                    )
                    return
                if "/wait" in self.path:
                    self._respond(204)
                    return
                if self.path == "/api/credential":
                    payload = json.loads(body)
                    entry = {
                        "id": f"cred_{len(outer.credentials) + 1:03d}",
                        "integrationID": payload.get("integrationID", "opencode"),
                        "label": payload.get("label", ""),
                        "active": False,
                        "value": payload.get("value", {}),
                    }
                    outer.credentials.append(entry)
                    outer.registered.append(payload)
                    self._respond(200, {"data": entry})
                    return
                if "/activate" in self.path:
                    credential_id = self.path.split("/")[3]
                    for entry in outer.credentials:
                        entry["active"] = entry["id"] == credential_id
                    outer.active_credential = credential_id
                    outer.activated.append(credential_id)
                    self._respond(204)
                    return
                self._respond(404, {"message": "not found"})

            def do_DELETE(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                self._respond(200, {"data": True})

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

    def add_credential(self, credential_id: str, key: str, active: bool = True) -> None:
        self.credentials.append(
            {
                "id": credential_id,
                "integrationID": "opencode",
                "label": credential_id,
                "active": active,
                "value": {"type": "key", "key": key},
            }
        )
        if active:
            self.active_credential = credential_id


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> _FakeService:
    monkeypatch.setenv("OPENCODE_SERVICE_PASSWORD", PASSWORD)
    fake = _FakeService()
    fake.start()
    yield fake
    fake.stop()


def _gateway(service: _FakeService, **overrides) -> OpenCodeGateway:
    settings: dict = {
        "provider": "opencode",
        "base_url": service.base_url,
        "timeout_seconds": 3.0,
    }
    settings.update(overrides)
    return OpenCodeGateway(GatewayConfig(**settings))


def _chat(text: str = "hi") -> ChatRequest:
    return ChatRequest(messages=[Message(role="user", content=text)])


def test_a_rate_limited_model_falls_over_to_the_next_model(service: _FakeService) -> None:
    service.quota_models = {"deepseek-v4.1-flash-free"}
    gateway = _gateway(service, model="opencode/deepseek-v4.1-flash-free")

    response = gateway.complete(_chat())

    assert response.text == "Model reply."
    assert service.received_models == ["deepseek-v4.1-flash-free", "beam-free"]


def test_every_model_rate_limited_reports_an_honest_error(service: _FakeService) -> None:
    service.quota_models = {"deepseek-v4.1-flash-free", "beam-free"}
    gateway = _gateway(service, model="opencode/deepseek-v4.1-flash-free")

    with pytest.raises(GatewayRateLimited) as excinfo:
        gateway.complete(_chat())

    message = excinfo.value.message
    assert "rate limited" in message.lower()
    # The student never learns which model or provider was involved.
    assert "deepseek" not in message.lower()
    assert "beam" not in message.lower()


def test_a_rate_limited_account_switches_to_the_next_stored_account(
    service: _FakeService,
) -> None:
    service.add_credential("cred_a", "key-a", active=True)
    service.add_credential("cred_b", "key-b", active=False)
    service.quota_accounts = {"cred_a"}
    gateway = _gateway(service, model="opencode/beam-free")

    response = gateway.complete(_chat())

    assert response.text == "Model reply."
    assert service.activated == ["cred_b"]
    # Same model, retried on the other account.
    assert service.received_models == ["beam-free", "beam-free"]


def test_configured_keys_are_registered_once_and_never_duplicated(
    service: _FakeService,
) -> None:
    service.add_credential("cred_a", "oc_key_already_there", active=True)
    gateway = _gateway(
        service,
        model="opencode/beam-free",
        account_keys=["oc_key_already_there", "oc_key_new_one"],
    )

    gateway.complete(_chat())
    gateway.complete(_chat())

    # The known key is reused, the new one is stored exactly once.
    assert [payload["value"]["key"] for payload in service.registered] == ["oc_key_new_one"]
    assert len(service.credentials) == 2


def test_rotation_can_be_switched_off(service: _FakeService) -> None:
    service.add_credential("cred_a", "key-a", active=True)
    service.add_credential("cred_b", "key-b", active=False)
    service.quota_accounts = {"cred_a"}
    gateway = _gateway(service, model="opencode/beam-free", rotate_credentials=False)

    with pytest.raises(GatewayRateLimited):
        gateway.complete(_chat())

    assert service.activated == []


def test_only_the_configured_accounts_are_used(service: _FakeService) -> None:
    service.add_credential("cred_a", "key-a", active=True)
    service.add_credential("cred_b", "key-b", active=False)
    service.add_credential("cred_c", "key-c", active=False)
    service.quota_accounts = {"cred_a"}
    gateway = _gateway(service, model="opencode/beam-free", account_keys=["key-b"])

    gateway.complete(_chat())

    # cred_c is not in the app's pool, so it is never activated.
    assert service.activated == ["cred_b"]


def test_a_model_proved_exhausted_is_not_repeated_on_the_next_turn(
    service: _FakeService,
) -> None:
    service.add_credential("cred_a", "key-a", active=True)
    service.quota_models = {"deepseek-v4.1-flash-free"}
    gateway = _gateway(service, model="opencode/deepseek-v4.1-flash-free")

    gateway.complete(_chat())
    first_turn = len(service.received_models)
    gateway.complete(_chat())
    second_turn = service.received_models[first_turn:]

    # The second turn starts with the model that works, not the one that
    # just proved to be out of quota.
    assert "deepseek-v4.1-flash-free" not in second_turn
    assert second_turn == ["beam-free"]
