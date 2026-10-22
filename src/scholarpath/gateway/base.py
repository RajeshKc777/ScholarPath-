"""Gateway-independent chat types.

The rest of the application depends on these types, never on a concrete
provider. Milestone 1 ships a stub; Milestone 2 adds the OpenCode adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, Sequence, runtime_checkable

Role = Literal["system", "user", "assistant"]
FinishReason = Literal["stop", "length", "error"]


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Message content cannot be empty.")


@dataclass(frozen=True, slots=True)
class ChatRequest:
    messages: Sequence[Message]
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.2

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("ChatRequest requires at least one message.")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive.")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2.")

    @property
    def last_user_message(self) -> Message:
        for message in reversed(self.messages):
            if message.role == "user":
                return message
        raise ValueError("ChatRequest contains no user message.")


@dataclass(frozen=True, slots=True)
class ChatResponse:
    text: str
    model: str
    finish_reason: FinishReason = "stop"
    usage: dict[str, int] = field(default_factory=dict)


class GatewayError(Exception):
    """Base class for gateway failures.

    ``retryable`` tells the orchestrator whether another attempt (or a fallback
    model) is worth trying. Errors are never swallowed into fake results.
    """

    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GatewayUnavailable(GatewayError):
    retryable = True


class GatewayTimeout(GatewayError):
    retryable = True


class GatewayRateLimited(GatewayError):
    retryable = True

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        # Seconds the provider asked us to wait, when it said so (Retry-After).
        self.retry_after = retry_after


class GatewayProtocolError(GatewayError):
    retryable = False


class GatewayForbidden(GatewayError):
    """The provider accepted the credential but refused this request (403).

    Not retried: a refusal is a policy or permission answer, not a transient
    failure. The router disables the profile for the session and moves on.
    """

    retryable = False


class GatewayNotConfigured(GatewayError):
    retryable = False


@runtime_checkable
class ModelGateway(Protocol):
    """Contract every model backend must satisfy."""

    name: str

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Return one completion. Raise GatewayError on failure."""
        ...
