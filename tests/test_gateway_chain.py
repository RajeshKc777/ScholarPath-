"""The provider chain: one provider exhausted, the next one answers."""

from __future__ import annotations

import pytest

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayForbidden,
    GatewayNotConfigured,
    GatewayRateLimited,
    Message,
)
from scholarpath.gateway.chain import GatewayChain


class _Gateway:
    """A gateway double that either answers or fails."""

    name = "first"

    def __init__(self, error: Exception | None = None, text: str = "Answered.") -> None:
        self.error = error
        self.text = text
        self.calls = 0

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ChatResponse(text=self.text, model="test/model")


def _chat() -> ChatRequest:
    return ChatRequest(messages=[Message(role="user", content="hi")])


def test_the_first_gateway_answers_when_it_can() -> None:
    first = _Gateway()
    second = _Gateway(text="Second answer.")
    chain = GatewayChain([first, second])

    response = chain.complete(_chat())

    assert response.text == "Answered."
    assert second.calls == 0


def test_a_rate_limited_provider_hands_over_to_the_next_one() -> None:
    first = _Gateway(error=GatewayRateLimited("rate limited"))
    second = _Gateway(text="Second answer.")
    chain = GatewayChain([first, second])

    response = chain.complete(_chat())

    assert response.text == "Second answer."
    assert first.calls == 1
    assert second.calls == 1


def test_a_broken_configuration_stops_the_chain_immediately() -> None:
    first = _Gateway(error=GatewayNotConfigured("no key"))
    second = _Gateway()
    chain = GatewayChain([first, second])

    with pytest.raises(GatewayNotConfigured):
        chain.complete(_chat())

    assert second.calls == 0


def test_a_refused_request_moves_on_to_the_next_provider() -> None:
    # A 403 answers one provider, not the request: the next one may serve it.
    first = _Gateway(error=GatewayForbidden("refused by the provider"))
    second = _Gateway(text="Second answer.")
    chain = GatewayChain([first, second])

    response = chain.complete(_chat())

    assert response.text == "Second answer."
    assert second.calls == 1


def test_a_refusal_by_every_provider_is_reported() -> None:
    first = _Gateway(error=GatewayForbidden("refused"))
    second = _Gateway(error=GatewayForbidden("also refused"))
    chain = GatewayChain([first, second])

    with pytest.raises(GatewayForbidden) as excinfo:
        chain.complete(_chat())

    assert "also refused" in excinfo.value.message


def test_every_provider_failing_reports_the_last_error() -> None:
    first = _Gateway(error=GatewayRateLimited("first is limited"))
    second = _Gateway(error=GatewayRateLimited("second is limited"))
    chain = GatewayChain([first, second])

    with pytest.raises(GatewayRateLimited) as excinfo:
        chain.complete(_chat())

    assert "second is limited" in excinfo.value.message


def test_the_chain_reports_every_provider_name() -> None:
    first = _Gateway()
    first.name = "opencode"
    second = _Gateway()
    second.name = "openai"
    chain = GatewayChain([first, second])

    assert chain.name == "opencode"
    assert chain.provider_names == ("opencode", "openai")
