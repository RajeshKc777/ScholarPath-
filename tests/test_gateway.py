"""Gateway contract: explicit types, honest stub, no silent provider downgrade."""

from __future__ import annotations

import pytest

from scholarpath.config import GatewayConfig
from scholarpath.gateway import (
    ChatRequest,
    ChatResponse,
    GatewayNotConfigured,
    Message,
    ModelGateway,
    OpenCodeGateway,
    StubGateway,
    build_gateway,
)


def test_stub_satisfies_the_contract() -> None:
    assert isinstance(StubGateway(), ModelGateway)


def test_stub_is_deterministic_and_admits_what_it_is() -> None:
    gateway = StubGateway()
    request = ChatRequest(messages=[Message(role="user", content="Find me a PhD scholarship")])

    first = gateway.complete(request)
    second = gateway.complete(request)

    assert first.text == second.text
    assert isinstance(first, ChatResponse)
    assert "Offline stub gateway" in first.text
    assert "No scholarship research" in first.text
    assert "Find me a PhD scholarship" in first.text
    assert first.model == "stub/deterministic"


def test_request_requires_messages() -> None:
    with pytest.raises(ValueError):
        ChatRequest(messages=[])


def test_message_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        Message(role="user", content="   ")


def test_request_rejects_impossible_parameters() -> None:
    message = Message(role="user", content="hi")

    with pytest.raises(ValueError):
        ChatRequest(messages=[message], max_tokens=0)
    with pytest.raises(ValueError):
        ChatRequest(messages=[message], temperature=9.0)


def test_response_usage_is_not_shared_between_instances() -> None:
    first = ChatResponse(text="a", model="m")
    first.usage["prompt_tokens"] = 5

    assert ChatResponse(text="b", model="m").usage == {}


def test_factory_builds_the_stub() -> None:
    gateway = build_gateway(GatewayConfig(provider="stub", model=""))

    assert isinstance(gateway, StubGateway)


def test_factory_builds_opencode_gateway_when_service_known(tmp_path) -> None:
    registration = tmp_path / "service.json"
    registration.write_text(
        '{"url": "http://127.0.0.1:4096", "password": "pw"}', encoding="utf-8"
    )

    gateway = build_gateway(
        GatewayConfig(provider="opencode", service_file=str(registration))
    )

    assert isinstance(gateway, OpenCodeGateway)
    assert gateway.base_url == "http://127.0.0.1:4096"


def test_factory_opencode_fails_loudly_without_a_service(tmp_path) -> None:
    with pytest.raises(GatewayNotConfigured) as excinfo:
        build_gateway(
            GatewayConfig(provider="opencode", service_file=str(tmp_path / "absent.json"))
        )

    assert "OpenCode" in str(excinfo.value)
