"""Quota-aware routing across independently configured providers (G191).

The app can hold several provider profiles at once - a local model, a free
cloud tier, a paid endpoint the student added themselves. This router decides
which one answers, in configuration order, and keeps the decision honest:

- a rate-limited provider (HTTP 429) is put on a cooldown taken from its
  ``Retry-After`` header, so the next turn does not ask it again immediately;
- a provider whose key was rejected (401), whose request was refused (403), or
  whose configuration is unusable is disabled for the session, never retried
  in a loop;
- a missing model on one provider is not fatal: the next provider may have it;
- ``free_only`` mode only considers profiles marked free-only, so a free user
  can never be routed to a paid endpoint by a fallback;
- the conversation is the same ``ChatRequest`` object on every attempt. The
  router never trims, rewrites, or stores history - that belongs to the app.

No account rotation to evade limits happens here: profiles are accounts the
student legitimately connected.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayError,
    GatewayForbidden,
    GatewayNotConfigured,
    GatewayRateLimited,
    ModelGateway,
)

logger = logging.getLogger("scholarpath.gateway.router")

DEFAULT_COOLDOWN_SECONDS = 60.0
MAX_COOLDOWN_SECONDS = 3600.0

ProviderState = Literal["ready", "cooling_down", "disabled"]


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """One named gateway plus its routing flags."""

    name: str
    gateway: ModelGateway
    free_only: bool = False
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """Read-only view for logs and settings; never contains a secret."""

    name: str
    free_only: bool
    state: ProviderState
    cooldown_seconds: float = 0.0
    detail: str = ""


@dataclass
class _State:
    cooldown_until: float = 0.0
    disabled: bool = False
    detail: str = ""


class ProviderRouter:
    """Ordered, quota-aware routing across provider profiles."""

    name = "router"

    def __init__(
        self,
        profiles: Sequence[ProviderProfile],
        *,
        free_only: bool = False,
        default_cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not profiles:
            raise ValueError("A provider router needs at least one profile.")
        self._profiles = tuple(profiles)
        self._free_only = bool(free_only)
        self._default_cooldown = max(1.0, float(default_cooldown_seconds))
        self._clock = clock or time.monotonic
        self._states: dict[str, _State] = {
            profile.name: _State() for profile in self._profiles
        }

    # -- protocol ----------------------------------------------------------
    @property
    def provider_names(self) -> tuple[str, ...]:
        """Every name that must be scrubbed from a reply (profile + adapter)."""
        names: list[str] = []
        for profile in self._profiles:
            for name in (profile.name, profile.gateway.name):
                if name and name not in names:
                    names.append(name)
        return tuple(names)

    @property
    def free_only(self) -> bool:
        return self._free_only

    def __len__(self) -> int:
        return len(self._profiles)

    def complete(self, request: ChatRequest) -> ChatResponse:
        now = self._clock()
        eligible = self._eligible()
        if not eligible:
            raise self._nothing_eligible()

        last_error: GatewayError | None = None
        cooling: list[float] = []

        for profile in eligible:
            state = self._states[profile.name]
            if state.disabled:
                continue
            remaining = state.cooldown_until - now
            if remaining > 0:
                cooling.append(remaining)
                continue

            attempted = True
            attempted = True
            try:
                return profile.gateway.complete(self._profile_request(request))
            except GatewayRateLimited as exc:
                wait = self._cooldown_seconds(exc.retry_after)
                state.cooldown_until = now + wait
                state.detail = exc.message
                last_error = exc
                cooling.append(wait)
                logger.info(
                    "provider %s is cooling down for %.0fs (%s)",
                    profile.name,
                    wait,
                    exc.message,
                )
            except (GatewayNotConfigured, GatewayForbidden) as exc:
                state.disabled = True
                state.detail = exc.message
                last_error = exc
                logger.info(
                    "provider %s disabled for this session (%s)",
                    profile.name,
                    exc.message,
                )
            except GatewayError as exc:
                if not exc.retryable:
                    raise
                state.detail = exc.message
                last_error = exc
                logger.info(
                    "provider %s could not answer (%s); trying the next one",
                    profile.name,
                    exc.message,
                )

        if cooling and (last_error is None or isinstance(last_error, GatewayRateLimited)):
            wait = min(cooling)
            raise GatewayRateLimited(
                "Every connected model provider is rate limited or cooling down. "
                f"Try again in {max(1, int(wait + 0.999))}s.",
                retry_after=wait,
            )
        if last_error is not None:
            raise last_error
        raise GatewayNotConfigured(
            "No connected model provider is usable. Check the provider profiles "
            "in config.toml or connect a provider."
        )

    # -- status ------------------------------------------------------------
    def status(self) -> tuple[ProviderStatus, ...]:
        now = self._clock()
        rows: list[ProviderStatus] = []
        for profile in self._profiles:
            state = self._states[profile.name]
            if not profile.enabled:
                rows.append(
                    ProviderStatus(
                        name=profile.name,
                        free_only=profile.free_only,
                        state="disabled",
                        detail="disabled in config",
                    )
                )
                continue
            if state.disabled:
                rows.append(
                    ProviderStatus(
                        name=profile.name,
                        free_only=profile.free_only,
                        state="disabled",
                        detail=state.detail,
                    )
                )
                continue
            remaining = max(0.0, state.cooldown_until - now)
            if remaining > 0:
                rows.append(
                    ProviderStatus(
                        name=profile.name,
                        free_only=profile.free_only,
                        state="cooling_down",
                        cooldown_seconds=round(remaining, 1),
                        detail=state.detail,
                    )
                )
                continue
            rows.append(
                ProviderStatus(
                    name=profile.name,
                    free_only=profile.free_only,
                    state="ready",
                    detail=state.detail,
                )
            )
        return tuple(rows)

    # -- internals ---------------------------------------------------------
    @staticmethod
    def _profile_request(request: ChatRequest) -> ChatRequest:
        """Each profile answers with its own configured model, not a global one."""
        if request.model is None:
            return request
        return ChatRequest(
            messages=request.messages,
            model=None,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

    def _eligible(self) -> list[ProviderProfile]:
        return [
            profile
            for profile in self._profiles
            if profile.enabled and (not self._free_only or profile.free_only)
        ]

    def _nothing_eligible(self) -> GatewayNotConfigured:
        if self._free_only:
            return GatewayNotConfigured(
                "Free-only mode is on, but no provider profile is marked "
                "free_only. Add a free profile or turn free_only off in config.toml."
            )
        return GatewayNotConfigured(
            "No model provider profile is enabled. Add one to config.toml."
        )

    def _cooldown_seconds(self, retry_after: float | None) -> float:
        if retry_after is None or retry_after <= 0:
            return self._default_cooldown
        return min(max(float(retry_after), 1.0), MAX_COOLDOWN_SECONDS)
