"""The provider router: ordering, cooldowns, fallback and free-only mode (G191).

Every gateway here is a double. No network beyond loopback, no real key, no
real quota: the test proves the router's decisions, not a provider's uptime.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import ValidationError

from scholarpath.config import GatewayConfig, ProviderProfileConfig
from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayForbidden,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayUnavailable,
    Message,
)
from scholarpath.gateway.factory import build_gateway
from scholarpath.gateway.router import ProviderProfile, ProviderRouter


class _Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class _Gateway:
    """A gateway double: answers, or raises the errors it was given in order."""

    def __init__(
        self,
        name: str = "fake",
        text: str = "Answered.",
        errors: list[Exception] | None = None,
    ) -> None:
        self.name = name
        self.text = text
        self.errors = list(errors or [])
        self.requests: list[ChatRequest] = []

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        if self.errors:
            raise self.errors.pop(0)
        return ChatResponse(text=self.text, model=f"{self.name}/model")


def _chat() -> ChatRequest:
    return ChatRequest(messages=[Message(role="user", content="hi")])


def _router(
    *profiles: ProviderProfile,
    free_only: bool = False,
    clock: _Clock | None = None,
) -> ProviderRouter:
    return ProviderRouter(list(profiles), free_only=free_only, clock=clock or _Clock())


def test_the_first_eligible_provider_answers() -> None:
    first = _Gateway(text="First.")
    second = _Gateway(text="Second.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
    )

    response = router.complete(_chat())

    assert response.text == "First."
    assert second.requests == []


def test_a_rate_limited_provider_cools_down_before_it_is_tried_again() -> None:
    clock = _Clock()
    first = _Gateway(errors=[GatewayRateLimited("slow down", retry_after=30)])
    second = _Gateway(text="Fallback.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
        clock=clock,
    )

    assert router.complete(_chat()).text == "Fallback."
    assert len(first.requests) == 1

    clock.now += 29.0
    assert router.complete(_chat()).text == "Fallback."
    assert len(first.requests) == 1  # still cooling

    clock.now += 2.0
    assert router.complete(_chat()).text == "Answered."
    assert len(first.requests) == 2  # eligible again


def test_a_rate_limit_without_a_header_uses_the_default_cooldown() -> None:
    clock = _Clock()
    first = _Gateway(errors=[GatewayRateLimited("slow down")])
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", _Gateway()),
        clock=clock,
    )

    router.complete(_chat())

    status = router.status()[0]
    assert status.state == "cooling_down"
    assert status.cooldown_seconds == 60.0


def test_a_rejected_key_disables_the_provider_for_the_session() -> None:
    first = _Gateway(errors=[GatewayNotConfigured("bad key")])
    second = _Gateway(text="Fallback.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
    )

    assert router.complete(_chat()).text == "Fallback."
    assert router.complete(_chat()).text == "Fallback."

    assert len(first.requests) == 1
    assert router.status()[0].state == "disabled"


def test_a_forbidden_provider_is_disabled_not_retried() -> None:
    first = _Gateway(errors=[GatewayForbidden("refused")])
    second = _Gateway(text="Fallback.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
    )

    router.complete(_chat())
    router.complete(_chat())

    assert len(first.requests) == 1
    assert router.status()[0].state == "disabled"


def test_free_only_mode_never_calls_a_paid_provider() -> None:
    paid = _Gateway(text="Paid.")
    free = _Gateway(text="Free.")
    router = _router(
        ProviderProfile("paid", paid, free_only=False),
        ProviderProfile("free", free, free_only=True),
        free_only=True,
    )

    response = router.complete(_chat())

    assert response.text == "Free."
    assert paid.requests == []


def test_free_only_mode_without_a_free_profile_says_so() -> None:
    router = _router(
        ProviderProfile("paid", _Gateway(), free_only=False),
        free_only=True,
    )

    with pytest.raises(GatewayNotConfigured) as excinfo:
        router.complete(_chat())

    message = excinfo.value.message.lower()
    assert "free-only" in message
    assert "free_only" in message


def test_the_fallback_receives_the_same_conversation() -> None:
    first = _Gateway(errors=[GatewayRateLimited("slow down")])
    second = _Gateway(text="Fallback.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
    )
    request = ChatRequest(
        messages=[
            Message(role="system", content="You are ScholarPath."),
            Message(role="user", content="Which scholarships fit me?"),
            Message(role="assistant", content="Tell me your degree level."),
            Message(role="user", content="Masters."),
        ],
        model="global/model",
        max_tokens=512,
        temperature=0.4,
    )

    router.complete(request)

    forwarded = second.requests[0]
    assert forwarded.messages == request.messages
    assert forwarded.max_tokens == 512
    assert forwarded.temperature == 0.4
    # The profile answers with its own configured model; a global override is
    # not sent to a provider that may not host it.
    assert forwarded.model is None


def test_every_cooling_provider_reports_the_shortest_wait() -> None:
    router = _router(
        ProviderProfile(
            "one", _Gateway(errors=[GatewayRateLimited("slow", retry_after=20)])
        ),
        ProviderProfile(
            "two", _Gateway(errors=[GatewayRateLimited("slow", retry_after=45)])
        ),
    )

    with pytest.raises(GatewayRateLimited) as excinfo:
        router.complete(_chat())

    assert excinfo.value.retry_after == 20.0
    assert "cooling down" in excinfo.value.message.lower()


def test_a_retryable_failure_moves_on_to_the_next_provider() -> None:
    first = _Gateway(errors=[GatewayUnavailable("down")])
    second = _Gateway(text="Fallback.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
    )

    assert router.complete(_chat()).text == "Fallback."


def test_a_non_retryable_failure_is_not_hidden_by_a_fallback() -> None:
    first = _Gateway(errors=[GatewayProtocolError("broken payload")])
    second = _Gateway(text="Fallback.")
    router = _router(
        ProviderProfile("one", first),
        ProviderProfile("two", second),
    )

    with pytest.raises(GatewayProtocolError):
        router.complete(_chat())

    assert second.requests == []


def test_status_reports_ready_cooling_and_disabled_states() -> None:
    clock = _Clock()
    limited = _Gateway(errors=[GatewayRateLimited("slow", retry_after=30)])
    broken = _Gateway(errors=[GatewayNotConfigured("bad key")])
    healthy = _Gateway(name="healthy")
    router = _router(
        ProviderProfile("limited", limited),
        ProviderProfile("broken", broken),
        ProviderProfile("healthy", healthy),
        clock=clock,
    )

    router.complete(_chat())
    rows = {row.name: row for row in router.status()}

    assert rows["limited"].state == "cooling_down"
    assert rows["limited"].cooldown_seconds == 30.0
    assert rows["broken"].state == "disabled"
    assert rows["healthy"].state == "ready"


def test_the_router_reports_names_that_must_be_redacted() -> None:
    router = _router(ProviderProfile("work", _Gateway(name="openai")))

    assert router.name == "router"
    assert router.provider_names == ("work", "openai")


def test_an_empty_router_is_refused() -> None:
    with pytest.raises(ValueError):
        ProviderRouter([])


# -- configuration ---------------------------------------------------------


def test_profile_names_must_be_unique() -> None:
    with pytest.raises(ValidationError):
        GatewayConfig(
            profiles=[
                ProviderProfileConfig(name="same", kind="stub"),
                ProviderProfileConfig(name="same", kind="stub"),
            ]
        )


def test_an_openai_profile_needs_a_base_url_and_a_model() -> None:
    with pytest.raises(ValidationError):
        ProviderProfileConfig(name="cloud", kind="openai")
    with pytest.raises(ValidationError):
        ProviderProfileConfig(
            name="cloud",
            kind="openai",
            base_url="https://example.test/v1",
        )


def test_profiles_take_precedence_over_the_single_provider() -> None:
    config = GatewayConfig(
        provider="stub",
        profiles=[
            ProviderProfileConfig(
                name="offline",
                kind="stub",
                model="stub/deterministic",
                free_only=True,
            )
        ],
    )

    gateway = build_gateway(config)

    assert isinstance(gateway, ProviderRouter)
    assert len(gateway) == 1
    assert gateway.complete(_chat()).text


class _Endpoint:
    """Minimal loopback OpenAI-compatible endpoint for factory tests."""

    def __init__(self, reply: str = "Endpoint reply.", status: int = 200) -> None:
        self.reply = reply
        self.status = status
        self.auth: list[str | None] = []
        self.models: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length) or b"{}")
                model = str(payload.get("model") or "")
                outer.auth.append(self.headers.get("Authorization"))
                outer.models.append(model)
                if outer.status != 200:
                    raw = json.dumps({"error": {"message": "status"}}).encode()
                else:
                    raw = json.dumps(
                        {
                            "model": model,
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": outer.reply,
                                    },
                                    "finish_reason": "stop",
                                }
                            ],
                        }
                    ).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self._http.server_address[1])
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __enter__(self) -> _Endpoint:
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._http.shutdown()
        self._http.server_close()


def test_two_profiles_use_their_own_endpoint_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A key in the global variable must never reach a profile's endpoint.
    monkeypatch.setenv("SCHOLARPATH_API_KEYS", "global-key-that-must-not-leak")
    with _Endpoint(status=429) as first, _Endpoint(reply="Second.") as second:
        config = GatewayConfig(
            profiles=[
                ProviderProfileConfig(
                    name="first",
                    kind="openai",
                    base_url=first.base_url,
                    model="first-model",
                    api_keys=["key-a"],
                ),
                ProviderProfileConfig(
                    name="second",
                    kind="openai",
                    base_url=second.base_url,
                    model="second-model",
                    api_keys=["key-b"],
                ),
            ]
        )
        gateway = build_gateway(config)

        response = gateway.complete(_chat())

    assert response.text == "Second."
    assert first.auth == ["Bearer key-a"]
    assert second.auth == ["Bearer key-b"]
    assert first.models == ["first-model"]
    assert second.models == ["second-model"]
