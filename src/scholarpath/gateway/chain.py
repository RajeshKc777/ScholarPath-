"""A chain of gateways.

One provider can be exhausted - every model rate-limited, the service down,
the account quota spent. The app then tries the next configured provider
instead of ending the turn with an error. The first gateway that answers
wins; nothing is merged or invented.

A non-retryable failure (a wrong key, a broken configuration) stops the
chain immediately: repeating it on another provider would only produce the
same mistake twice.
"""

from __future__ import annotations

import logging

from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayError,
    ModelGateway,
)

logger = logging.getLogger("scholarpath.gateway.chain")


class GatewayChain:
    """Several gateways in order. The first that answers wins."""

    def __init__(self, gateways: list[ModelGateway]) -> None:
        if not gateways:
            raise ValueError("A gateway chain needs at least one gateway.")
        self._gateways = list(gateways)

    @property
    def name(self) -> str:  # noqa: D401 - protocol attribute
        """The first gateway's name - the one that usually answers."""
        return self._gateways[0].name

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Every provider in the chain (used by the identity guard)."""
        return tuple(gateway.name for gateway in self._gateways)

    def complete(self, request: ChatRequest) -> ChatResponse:
        last_error: GatewayError | None = None
        for index, gateway in enumerate(self._gateways):
            try:
                return gateway.complete(request)
            except GatewayError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
                logger.info(
                    "provider %s could not answer (%s); trying the next one",
                    gateway.name,
                    exc.message,
                )
                if index + 1 >= len(self._gateways):
                    break
        if last_error is not None:
            raise last_error
        raise GatewayError("No provider was available.")

    def __len__(self) -> int:
        return len(self._gateways)
