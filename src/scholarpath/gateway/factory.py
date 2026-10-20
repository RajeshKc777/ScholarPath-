"""Gateway construction from configuration.

Selection is explicit. A provider that is configured but not implemented raises
instead of silently degrading to the stub - a silent swap would make the app
look like it queried real sources when it did not.
"""

from __future__ import annotations

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import GatewayNotConfigured, ModelGateway
from scholarpath.gateway.opencode import OpenCodeGateway
from scholarpath.gateway.stub import StubGateway


def build_gateway(config: GatewayConfig) -> ModelGateway:
    if config.provider == "stub":
        return StubGateway(model=config.model or "stub/deterministic")

    if config.provider == "opencode":
        return OpenCodeGateway(config)

    raise GatewayNotConfigured(f"Unknown gateway provider: {config.provider!r}.")
