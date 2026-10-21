"""Gateway construction from configuration.

Selection is explicit. A provider that is configured but not implemented raises
instead of silently degrading to the stub - a silent swap would make the app
look like it queried real sources when it did not.

``fallback_providers`` turns the app's gateway into a chain: the first
provider answers when it can, and the next one takes over when the first is
rate limited or unreachable.
"""

from __future__ import annotations

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import GatewayNotConfigured, ModelGateway
from scholarpath.gateway.chain import GatewayChain
from scholarpath.gateway.openai_compat import OpenAICompatibleGateway
from scholarpath.gateway.opencode import OpenCodeGateway
from scholarpath.gateway.stub import StubGateway


def _build_one(provider: str, config: GatewayConfig) -> ModelGateway:
    if provider == "stub":
        return StubGateway(model=config.model or "stub/deterministic")

    if provider == "opencode":
        return OpenCodeGateway(config)

    if provider == "openai":
        return OpenAICompatibleGateway(config)

    raise GatewayNotConfigured(f"Unknown gateway provider: {provider!r}.")


def build_gateway(config: GatewayConfig) -> ModelGateway:
    """The configured gateway, or a chain of them."""
    primary = _build_one(config.provider, config)
    fallbacks = [
        _build_one(name, config) for name in config.fallback_providers if name != config.provider
    ]
    if not fallbacks:
        return primary
    return GatewayChain([primary, *fallbacks])
