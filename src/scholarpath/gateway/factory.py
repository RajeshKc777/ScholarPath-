"""Gateway construction from configuration.

Selection is explicit. A provider that is configured but not implemented raises
instead of silently degrading to the stub - a silent swap would make the app
look like it queried real sources when it did not.

Two shapes are supported:

- ``fallback_providers`` turns the app's gateway into a chain of provider
  kinds that share one configuration;
- ``profiles`` (G191) gives every provider its own endpoint, model chain and
  keys, behind a quota-aware router. When at least one profile is enabled it
  takes precedence over the single-provider fields.
"""

from __future__ import annotations

import re

from scholarpath.config import GatewayConfig, ProviderProfileConfig
from scholarpath.gateway.base import GatewayNotConfigured, ModelGateway
from scholarpath.gateway.chain import GatewayChain
from scholarpath.gateway.openai_compat import OpenAICompatibleGateway
from scholarpath.gateway.opencode import OpenCodeGateway
from scholarpath.gateway.router import ProviderProfile, ProviderRouter
from scholarpath.gateway.stub import StubGateway


def _build_one(provider: str, config: GatewayConfig) -> ModelGateway:
    if provider == "stub":
        return StubGateway(model=config.model or "stub/deterministic")

    if provider == "opencode":
        return OpenCodeGateway(config)

    if provider == "openai":
        return OpenAICompatibleGateway(config)

    raise GatewayNotConfigured(f"Unknown gateway provider: {provider!r}.")


def _profile_env_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return f"SCHOLARPATH_{cleaned or 'PROFILE'}_API_KEYS"


def _profile_gateway(profile: ProviderProfileConfig, config: GatewayConfig) -> ModelGateway:
    """One independently configured endpoint for a profile."""
    timeout = profile.timeout_seconds or config.timeout_seconds

    if profile.kind == "stub":
        return StubGateway(model=profile.model or "stub/deterministic")

    if profile.kind == "opencode":
        settings = config.model_copy(
            update={
                "base_url": profile.base_url or config.base_url,
                "model": profile.model or config.model,
                "models": list(profile.models) or list(config.models),
                "timeout_seconds": timeout,
            }
        )
        return OpenCodeGateway(settings)

    if profile.kind == "openai":
        settings = config.model_copy(
            update={
                "provider": "openai",
                "api_base_url": profile.base_url.strip(),
                "api_model": profile.model,
                "api_models": list(profile.models),
                "api_keys": list(profile.api_keys),
                # Profile keys come from the profile or its own variable - never
                # from the global key list, which may belong to another host.
                "api_keys_env": _profile_env_name(profile.name),
                "timeout_seconds": timeout,
            }
        )
        return OpenAICompatibleGateway(settings)

    raise GatewayNotConfigured(
        f"Unknown gateway profile kind: {profile.kind!r}."
    )


def build_gateway(config: GatewayConfig) -> ModelGateway:
    """The configured gateway: a profile router, a chain, or one provider."""
    enabled = [profile for profile in config.profiles if profile.enabled]
    if config.profiles and not enabled:
        raise GatewayNotConfigured(
            "Every gateway profile is disabled. Enable one in config.toml."
        )
    if enabled:
        return ProviderRouter(
            [
                ProviderProfile(
                    name=profile.name,
                    gateway=_profile_gateway(profile, config),
                    # A stub costs nothing, so free-only mode may use it.
                    free_only=profile.free_only or profile.kind == "stub",
                )
                for profile in enabled
            ],
            free_only=config.free_only,
        )

    primary = _build_one(config.provider, config)
    fallbacks = [
        _build_one(name, config) for name in config.fallback_providers if name != config.provider
    ]
    if not fallbacks:
        return primary
    return GatewayChain([primary, *fallbacks])
