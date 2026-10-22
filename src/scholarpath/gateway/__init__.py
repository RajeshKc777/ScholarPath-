"""Model gateway implementations and the provider-neutral contract."""

from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayError,
    GatewayForbidden,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
    Message,
    ModelGateway,
)
from scholarpath.gateway.factory import build_gateway
from scholarpath.gateway.opencode import OpenCodeGateway
from scholarpath.gateway.registry import ModelEntry, ModelRef, ModelRegistry
from scholarpath.gateway.router import ProviderProfile, ProviderRouter, ProviderStatus
from scholarpath.gateway.stub import StubGateway

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "GatewayError",
    "GatewayForbidden",
    "GatewayNotConfigured",
    "GatewayProtocolError",
    "GatewayRateLimited",
    "GatewayTimeout",
    "GatewayUnavailable",
    "Message",
    "ModelEntry",
    "ModelGateway",
    "ModelRef",
    "ModelRegistry",
    "OpenCodeGateway",
    "ProviderProfile",
    "ProviderRouter",
    "ProviderStatus",
    "StubGateway",
    "build_gateway",
]
