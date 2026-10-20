"""Model gateway implementations and the provider-neutral contract."""

from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayError,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
    Message,
    ModelGateway,
)
from scholarpath.gateway.factory import build_gateway
from scholarpath.gateway.stub import StubGateway

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "GatewayError",
    "GatewayNotConfigured",
    "GatewayProtocolError",
    "GatewayRateLimited",
    "GatewayTimeout",
    "GatewayUnavailable",
    "Message",
    "ModelGateway",
    "StubGateway",
    "build_gateway",
]
