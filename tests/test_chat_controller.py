"""Chat turn handling: ordering, busy state, and honest failure surfacing."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from scholarpath.gateway import (
    ChatRequest,
    ChatResponse,
    GatewayRateLimited,
    GatewayUnavailable,
    Message,
)
from scholarpath.gateway.stub import StubGateway
from scholarpath.ui.chat_controller import ChatController


def run_inline(work: Callable[[], None]) -> None:
    work()


class RecordingGateway:
    name = "recording"

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(text="noted", model="recording/v1")


class FailingGateway:
    name = "failing"

    def __init__(self, error: Exception) -> None:
        self._error = error

    def complete(self, request: ChatRequest) -> ChatResponse:
        raise self._error


def make_controller(gateway, **kwargs) -> ChatController:
    return ChatController(gateway, dispatch=run_inline, **kwargs)


def test_send_appends_user_then_assistant() -> None:
    controller = make_controller(StubGateway())

    assert controller.send("hello") is True

    roles = [turn.role for turn in controller.history]
    assert roles == ["user", "assistant"]
    assert controller.history[0].text == "hello"
    assert controller.history[1].error is False
    assert controller.busy is False


def test_busy_transitions_are_reported() -> None:
    controller = make_controller(StubGateway())
    states: list[bool] = []
    controller.busy_changed.connect(states.append)

    controller.send("hi")

    assert states == [True, False]


def test_blank_message_is_ignored() -> None:
    controller = make_controller(StubGateway())

    assert controller.send("   ") is False
    assert controller.history == ()


def test_second_send_is_ignored_while_busy() -> None:
    pending: list[Callable[[], None]] = []
    controller = ChatController(StubGateway(), dispatch=pending.append)

    assert controller.send("first") is True
    assert controller.busy is True
    assert controller.send("second") is False

    pending[0]()
    assert controller.busy is False
    assert [turn.role for turn in controller.history] == ["user", "assistant"]


def test_history_is_sent_to_the_gateway() -> None:
    gateway = RecordingGateway()
    controller = make_controller(gateway)

    controller.send("first question")
    controller.send("second question")

    assert len(gateway.requests) == 2
    second = gateway.requests[1]
    assert [message.role for message in second.messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert second.messages[-1].content == "second question"
    assert second.messages[0] == Message(role="user", content="first question")


def test_rate_limit_is_surfaced_without_fake_content() -> None:
    controller = make_controller(FailingGateway(GatewayRateLimited("429 too many requests")))
    failures: list[str] = []
    controller.failed.connect(failures.append)

    assert controller.send("hello") is True

    assistant = controller.history[-1]
    assert assistant.error is True
    assert "rate limiting" in assistant.text
    assert failures == ["429 too many requests"]
    assert controller.busy is False


def test_unavailable_provider_is_surfaced() -> None:
    controller = make_controller(FailingGateway(GatewayUnavailable("provider down")))

    controller.send("hello")

    assert controller.history[-1].error is True
    assert "unavailable" in controller.history[-1].text


def test_unexpected_exception_is_reported_as_error_turn() -> None:
    controller = make_controller(FailingGateway(RuntimeError("kaboom")))
    failures: list[str] = []
    controller.failed.connect(failures.append)

    controller.send("hello")

    assistant = controller.history[-1]
    assert assistant.error is True
    assert "kaboom" not in assistant.text
    assert failures and "Unexpected error" in failures[0]


def test_model_override_is_passed_through() -> None:
    gateway = RecordingGateway()
    controller = make_controller(gateway, model="stub/test-model")

    controller.send("hello")

    assert gateway.requests[0].model == "stub/test-model"
