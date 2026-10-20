"""Offline stub gateway used by Milestone 1.

It exists to prove the chat pipe end to end. It performs no research, opens no
network connection, and says so in every reply - it must never look like a real
scholarship answer.
"""

from __future__ import annotations

import time

from scholarpath.gateway.base import ChatRequest, ChatResponse, Message

BANNER = "Offline stub gateway (Milestone 1)."


class StubGateway:
    """Deterministic echo gateway. No network, no model, no fabrication."""

    name = "stub"

    def __init__(self, model: str = "stub/deterministic", latency_seconds: float = 0.0) -> None:
        self.model = model or "stub/deterministic"
        self._latency = max(0.0, latency_seconds)

    def complete(self, request: ChatRequest) -> ChatResponse:
        if self._latency:
            time.sleep(self._latency)

        user_text = request.last_user_message.content.strip()
        reply = (
            f"{BANNER}\n\n"
            f'I received: "{user_text}"\n\n'
            "No scholarship research has been performed. This build has no network "
            "access and no model behind it - real discovery and eligibility checks "
            "arrive in later milestones."
        )
        return ChatResponse(text=reply, model=self.model, finish_reason="stop")
