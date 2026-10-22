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
from scholarpath.identity import CANONICAL_REPLY, SYSTEM_PROMPT, forbidden_tokens, scrub_reply
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
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert second.messages[-1].content == "second question"
    assert second.messages[1] == Message(role="user", content="first question")


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


# -- G116: the AI never discloses its model or provider ---------------------------

class LeakyGateway:
    name = "opencode"

    def complete(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            text="I'm running as the **Beam Free** model (provider: opencode).",
            model="zai-org/glm-4.5",
        )


def test_identity_probe_never_reaches_gateway() -> None:
    gateway = RecordingGateway()
    controller = make_controller(gateway)
    controller.send("which model are you?")
    assert gateway.requests == []  # nothing that could disclose
    assert controller.history[-1].text == CANONICAL_REPLY


def test_direct_vendor_mention_is_intercepted() -> None:
    controller = make_controller(RecordingGateway())
    controller.send("are you Beam Free?")
    assert controller.history[-1].text == CANONICAL_REPLY


def test_system_prompt_precedes_history() -> None:
    gateway = RecordingGateway()
    controller = make_controller(gateway)
    controller.send("help me find funding")
    messages = gateway.requests[0].messages
    assert messages[0].role == "system"
    assert messages[0].content == SYSTEM_PROMPT
    assert [m.role for m in messages[1:]] == ["user"]


def test_leaky_reply_is_withheld_wholesale() -> None:
    controller = make_controller(LeakyGateway())
    controller.send("hello")
    assert controller.history[-1].text == CANONICAL_REPLY


def test_clean_unchanged() -> None:
    controller = make_controller(RecordingGateway())
    controller.send("hello")
    assert controller.history[-1].text == "noted"


def test_canonical_reply_leaks_nothing() -> None:
    tokens = forbidden_tokens("opencode", "zai-org/glm-4.5")
    scrubbed = scrub_reply(CANONICAL_REPLY, tokens)
    assert scrubbed == CANONICAL_REPLY


# -- G181: the chat knows what the profile already holds ------------------------


PROFILE = {
    "student_name": "Rajesh Katuwal",
    "degree_level": "bachelor",
    "gpa": "3.6",
    "gpa_scale": "4.0",
    "nationality": "Nepal",
    "preferred_countries": "Germany",
    "funding_need": "full funding",
    "ielts": "7.0",
}


def _summary_of(requests: list[ChatRequest]) -> str:
    """The profile summary the app sent, or "" when it sent none."""
    for message in requests[0].messages:
        if "Saved profile facts" in message.content:
            return message.content
    return ""


def test_the_profile_summary_is_sent_with_the_message() -> None:
    gateway = RecordingGateway()
    controller = make_controller(gateway, profile=lambda: dict(PROFILE))
    controller.send("what scholarships can I get?")

    summary = _summary_of(gateway.requests)
    assert "3.6" in summary
    assert "Nepal" in summary


def test_no_summary_is_sent_while_the_switch_is_off() -> None:
    gateway = RecordingGateway()
    controller = make_controller(
        gateway, profile=lambda: dict(PROFILE), context_enabled=False
    )
    controller.send("what scholarships can I get?")

    assert _summary_of(gateway.requests) == ""
    sent = " ".join(message.content for message in gateway.requests[0].messages)
    assert "Saved profile facts" not in sent


def test_the_name_never_leaves_the_device_with_the_summary() -> None:
    gateway = RecordingGateway()
    controller = make_controller(gateway, profile=lambda: dict(PROFILE))
    controller.send("hello")

    summary = _summary_of(gateway.requests)
    assert summary, "the summary was sent"
    assert "Rajesh" not in summary
    assert "Katuwal" not in summary


def test_a_broken_profile_never_breaks_the_chat() -> None:
    def broken() -> dict:
        raise RuntimeError("the database is locked")

    gateway = RecordingGateway()
    controller = make_controller(gateway, profile=broken)
    controller.send("hello")

    assert controller.history[-1].text == "noted"
