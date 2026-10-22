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

from scholarpath import __version__
from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import (
    ChatRequest,
    GatewayForbidden,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayUnavailable,
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
        self.received_user_agents: list[str | None] = []
        self.retry_after_by_model: dict[str, str] = {}
        self.message_by_model: dict[str, str] = {}
        self.raw_error_by_status: dict[int, str] = {}
        self.raw_response: str | None = None

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _respond(
                self,
                code: int,
                payload: str,
                headers: dict[str, str] | None = None,
            ) -> None:
                raw = payload.encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
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
                outer.received_user_agents.append(self.headers.get("User-Agent"))

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
                    payload_text = outer.raw_error_by_status.get(
                        status,
                        json.dumps(
                            {
                                "error": {
                                    "message": outer.message_by_model.get(
                                        model, f"status {status}"
                                    )
                                }
                            }
                        ),
                    )
                    headers = {}
                    if model in outer.retry_after_by_model:
                        headers["Retry-After"] = outer.retry_after_by_model[model]
                    self._respond(status, payload_text, headers)
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


def test_the_app_identifies_itself_with_a_user_agent(endpoint: _FakeEndpoint) -> None:
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    gateway.complete(_chat())

    assert endpoint.received_user_agents == [f"ScholarPath/{__version__}"]


def test_a_missing_key_is_reported_as_missing_not_rejected(
    endpoint: _FakeEndpoint,
) -> None:
    endpoint.require_key = True
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    with pytest.raises(GatewayNotConfigured) as excinfo:
        gateway.complete(_chat())

    message = excinfo.value.message.lower()
    assert "none is configured" in message
    assert "rejected" not in message


def test_a_forbidden_request_is_not_called_a_quota_limit(
    endpoint: _FakeEndpoint,
) -> None:
    endpoint.status_by_model["deepseek-v4-flash"] = 403
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        api_keys=["restricted-key"],
    )

    with pytest.raises(GatewayForbidden) as excinfo:
        gateway.complete(_chat())

    message = excinfo.value.message.lower()
    assert "refused" in message
    assert "not a quota limit" in message
    assert "rejected the configured" not in message


def test_a_cloudflare_client_block_is_not_reported_as_a_bad_key(
    endpoint: _FakeEndpoint,
) -> None:
    endpoint.status_by_model["deepseek-v4-flash"] = 403
    endpoint.raw_error_by_status[403] = '{"error": "error code: 1010"}'
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    with pytest.raises(GatewayUnavailable) as excinfo:
        gateway.complete(_chat())

    message = excinfo.value.message.lower()
    assert "1010" in message
    assert "not an authentication" in message


def test_a_missing_model_is_retried_on_the_next_model(endpoint: _FakeEndpoint) -> None:
    endpoint.status_by_model["retired-model"] = 404
    endpoint.message_by_model["retired-model"] = "model not found for this account"
    gateway = _gateway(
        endpoint,
        model="retired-model",
        models=["current-model"],
    )

    response = gateway.complete(_chat())

    assert response.text == "Model reply."
    assert endpoint.received_models == ["retired-model", "current-model"]


def test_a_missing_authorization_header_is_reported_as_an_auth_failure(
    endpoint: _FakeEndpoint,
) -> None:
    # Some providers answer 400 (not 401) when the key is missing.
    endpoint.status_by_model["deepseek-v4-flash"] = 400
    endpoint.message_by_model["deepseek-v4-flash"] = (
        "Missing or invalid Authorization header."
    )
    gateway = _gateway(endpoint, model="deepseek-v4-flash")

    with pytest.raises(GatewayNotConfigured) as excinfo:
        gateway.complete(_chat())

    message = excinfo.value.message.lower()
    assert "authorization" in message
    assert "missing or wrong" in message


def test_retry_after_is_read_from_the_header(endpoint: _FakeEndpoint) -> None:
    endpoint.status_by_model["deepseek-v4-flash"] = 429
    endpoint.retry_after_by_model["deepseek-v4-flash"] = "17"
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        failover_attempts=1,
    )

    with pytest.raises(GatewayRateLimited) as excinfo:
        gateway.complete(_chat())

    assert excinfo.value.retry_after == 17.0


def test_every_rejected_key_stops_before_an_unauthenticated_attempt(
    endpoint: _FakeEndpoint,
) -> None:
    endpoint.require_key = True
    endpoint.status_by_key["only-key"] = 401
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        api_keys=["only-key"],
    )

    with pytest.raises(GatewayNotConfigured):
        gateway.complete(_chat())

    assert endpoint.received_auth == ["Bearer only-key"]


def test_a_key_that_failed_last_turn_is_offered_again(
    endpoint: _FakeEndpoint,
) -> None:
    endpoint.require_key = True
    endpoint.status_by_key["recovering-key"] = 401
    gateway = _gateway(
        endpoint,
        model="deepseek-v4-flash",
        api_keys=["recovering-key"],
    )

    with pytest.raises(GatewayNotConfigured):
        gateway.complete(_chat())
    endpoint.status_by_key.pop("recovering-key")

    response = gateway.complete(_chat())

    assert response.text == "Model reply."
    assert endpoint.received_auth == ["Bearer recovering-key", "Bearer recovering-key"]
