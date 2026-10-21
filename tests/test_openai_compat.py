"""The OpenAI-compatible gateway against a fake endpoint.

The endpoint is a loopback double of any service that speaks
``POST /chat/completions``: a local router, a self-hosted server, a hosted
provider. What is tested is the app's behaviour - the reply is used as it
came, a rate limit moves on to the next model or key, and a broken endpoint
produces an honest error instead of an invented answer.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import ValidationError

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import (
    ChatRequest,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    Message,
)
from scholarpath.gateway.openai_compat import OpenAICompatibleGateway


class _FakeEndpoint:
    """Loopback OpenAI-compatible double with per-model failures."""

    def __init__(self) -> None:
        self.reply = "Model reply."
        self.status_by_model: dict[str, int] = {}
        self.status_by_key: dict[str, int] = {}
        self.body_by_model: dict[str, dict] = {}
        self.responses_only: set[str] = set()
        self.require_key = False
        self.received_models: list[str] = []
        self.received_paths: list[str] = []
        self.received_auth: list[str | None] = []
        self.raw_response: str | None = None

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _respond(self, code: int, payload: str) -> None:
                raw = payload.encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body or b"{}")
                model = str(payload.get("model") or "")
                outer.received_models.append(model)
                outer.received_paths.append(self.path)
                auth = self.headers.get("Authorization")
                outer.received_auth.append(auth)

                if self.path.endswith("/responses"):
                    self._respond(
                        200,
                        json.dumps(
                            {
                                "model": model,
                                "status": "completed",
                                "output": [
                                    {
                                        "type": "reasoning",
                                        "content": [],
                                    },
                                    {
                                        "type": "message",
                                        "content": [
                                            {"type": "output_text", "text": outer.reply}
                                        ],
                                    },
                                ],
                                "usage": {"input_tokens": 9, "output_tokens": 4},
                            }
                        ),
                    )
                    return

                if outer.require_key and not auth:
                    self._respond(401, json.dumps({"error": {"message": "no key"}}))
                    return

                token = (auth or "").removeprefix("Bearer ")
                if token in outer.status_by_key:
                    self._respond(
                        outer.status_by_key[token],
                        json.dumps({"error": {"message": "status"}}),
                    )
                    return

                if model in outer.responses_only:
                    self._respond(
                        400,
                        json.dumps(
                            {
                                "error": {
                                    "message": (
                                        f"Model {model} does not support "
                                        "/v1/chat/completions interface, please use "
                                        "/v1/responses"
                                    )
                                }
                            }
                        ),
                    )
                    return

                if outer.raw_response is not None:
                    self._respond(200, outer.raw_response)
                    return

                status = outer.status_by_model.get(model, 200)
                if status != 200:
                    self._respond(
                        status,
                        json.dumps({"error": {"message": f"status {status}"}}),
                    )
                    return
                if model in outer.body_by_model:
                    self._respond(200, json.dumps(outer.body_by_model[model]))
                    return
                self._respond(
                    200,
                    json.dumps(
                        {
                            "model": model,
                            "choices": [
                                {
                                    "message": {"role": "assistant", "content": outer.reply},
                                    "finish_reason": "stop",
                                }
                            ],
                            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
                        }
                    ),
                )

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self._http.server_address[1])
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._http.shutdown()
        self._http.server_close()


@pytest.fixture
def endpoint() -> _FakeEndpoint:
    fake = _FakeEndpoint()
    fake.start()
    yield fake
    fake.stop()


def _gateway(endpoint: _FakeEndpoint, **overrides) -> OpenAICompatibleGateway:
    settings: dict = {
        "provider": "openai",
        "api_base_url": endpoint.base_url,
        "timeout_seconds": 3.0,
    }
    settings.update(overrides)
    return OpenAICompatibleGateway(GatewayConfig(**settings))


def _chat(text: str = "hi") -> ChatRequest:
    return ChatRequest(messages=[Message(role="user", content=text)])


def test_a_reply_is_returned_as_it_came(endpoint: _FakeEndpoint) -> None:
    endpoint.reply = "DeepSeek says hello."
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    response = gateway.complete(_chat())

    assert response.text == "DeepSeek says hello."
    assert response.model == "deepseek-v4-flash"
    assert response.usage == {"input": 11, "output": 7}
    assert endpoint.received_models == ["deepseek-v4-flash"]


def test_the_configured_key_is_sent_as_a_bearer_token(endpoint: _FakeEndpoint) -> None:
    gateway = _gateway(endpoint, model="deepseek-v4-flash", api_keys=["secret-key"])

    gateway.complete(_chat())

    assert endpoint.received_auth == ["Bearer secret-key"]


def test_without_a_key_no_authorization_header_is_sent(endpoint: _FakeEndpoint) -> None:
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    gateway.complete(_chat())

    assert endpoint.received_auth == [None]


def test_a_rate_limited_model_moves_on_to_the_next_one(endpoint: _FakeEndpoint) -> None:
    endpoint.status_by_model["deepseek-v4-flash"] = 429
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        models=["glm-5.3-flash", "beam-free"],
    )

    response = gateway.complete(_chat())

    assert response.text == "Model reply."
    assert endpoint.received_models == ["deepseek-v4-flash", "glm-5.3-flash"]


def test_a_rejected_key_moves_on_to_the_next_key(endpoint: _FakeEndpoint) -> None:
    endpoint.require_key = True
    endpoint.status_by_key["bad-key"] = 401
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        api_keys=["bad-key", "good-key"],
    )

    response = gateway.complete(_chat())

    assert response.text == "Model reply."
    assert endpoint.received_auth == ["Bearer bad-key", "Bearer good-key"]


def test_every_model_rate_limited_reports_an_honest_error(endpoint: _FakeEndpoint) -> None:
    endpoint.status_by_model["deepseek-v4-flash"] = 429
    endpoint.status_by_model["glm-5.3-flash"] = 429
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        models=["glm-5.3-flash"],
        failover_attempts=4,
    )

    with pytest.raises(GatewayRateLimited) as excinfo:
        gateway.complete(_chat())

    assert "rate limited" in excinfo.value.message.lower()
    assert "deepseek" not in excinfo.value.message.lower()


def test_a_model_that_needs_the_responses_api_is_still_served(
    endpoint: _FakeEndpoint,
) -> None:
    endpoint.responses_only = {"gpt-6.1-sol"}
    endpoint.reply = "Responses reply."
    gateway = _gateway(endpoint, model="gpt-6.1-sol")

    response = gateway.complete(_chat())

    assert response.text == "Responses reply."
    assert response.usage == {"input": 9, "output": 4}
    assert endpoint.received_paths == ["/v1/chat/completions", "/v1/responses"]


def test_an_unreadable_response_is_reported_not_invented(endpoint: _FakeEndpoint) -> None:
    endpoint.raw_response = "{not json"
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    with pytest.raises(GatewayProtocolError):
        gateway.complete(_chat())


def test_the_provider_needs_a_base_url() -> None:
    with pytest.raises(ValidationError):
        GatewayConfig(provider="openai")


def test_an_unusable_base_url_is_refused() -> None:
    with pytest.raises(GatewayNotConfigured):
        OpenAICompatibleGateway(GatewayConfig(provider="openai", api_base_url="not-a-url"))
