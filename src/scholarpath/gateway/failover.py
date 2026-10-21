"""Failover helpers shared by the gateways.

The gateways decide *when* to fail over; these helpers decide *what to try
next* and keep the order deterministic (G104: routing is task-driven, never
arbitrary).

Two ideas live here:

- ``ModelChain`` - an ordered list of candidate models for one request. The
  primary model comes first, then the configured chain, then the free-tier
  alternatives offered by the provider. Paid models are never entered
  automatically: an unconfigured fallback must not spend money.
- ``KeyPool`` - an ordered list of API keys with rotation. The secret itself
  stays inside this object; callers only ever move an index forward.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scholarpath.gateway.registry import ModelRef, parse_model_ref

# Ids that mark a provider's free tier. Only these are used as automatic
# fallbacks, so a failed request can never turn into a bill.
FREE_TIER_SUFFIX = "-free"


@dataclass(frozen=True, slots=True)
class ModelChain:
    """Ordered candidate models for one task."""

    refs: tuple[ModelRef, ...] = ()

    @classmethod
    def from_ids(cls, ids: list[str] | tuple[str, ...]) -> ModelChain:
        """Parse model ids ("provider/model" or a bare id), keeping order."""
        refs: list[ModelRef] = []
        for text in ids:
            ref = parse_model_ref(text)
            if ref is None:
                continue
            if ref not in refs:
                refs.append(ref)
        return cls(tuple(refs))

    def plan(self, primary: ModelRef | None = None) -> tuple[ModelRef, ...]:
        """The attempt order: primary first, then the chain, no duplicates."""
        ordered: list[ModelRef] = []
        if primary is not None:
            ordered.append(primary)
        for ref in self.refs:
            if ref not in ordered:
                ordered.append(ref)
        return tuple(ordered)

    def __bool__(self) -> bool:
        return bool(self.refs)

    def __len__(self) -> int:
        return len(self.refs)


@dataclass
class KeyPool:
    """Ordered API keys with rotation.

    ``current`` returns the first key that has not been tried yet. A caller
    that fails marks the key as tried, so the next call moves on. The keys
    themselves are never logged.
    """

    keys: tuple[str, ...] = ()
    _tried: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        unique: list[str] = []
        for key in self.keys:
            cleaned = (key or "").strip()
            if cleaned and cleaned not in unique:
                unique.append(cleaned)
        self.keys = tuple(unique)

    def current(self) -> str | None:
        """The next key to try, or None when every key has been tried."""
        for key in self.keys:
            if key not in self._tried:
                return key
        return None

    def mark_tried(self, key: str) -> None:
        """Record that a key failed so the pool moves to the next one."""
        self._tried.add(key)

    def reset(self) -> None:
        """Forget the rotation history (used when a new request starts)."""
        self._tried.clear()

    def __len__(self) -> int:
        return len(self.keys)

    def __bool__(self) -> bool:
        return bool(self.keys)


def free_tier_alternatives(
    candidates: list[tuple[str, str]],
    exclude: ModelRef | None = None,
) -> tuple[ModelRef, ...]:
    """Free-tier models from a provider catalogue, in catalogue order.

    ``candidates`` are ``(provider, model_id)`` pairs. Only ids that mark a
    free tier are returned, so an automatic fallback never costs money.
    """
    refs: list[ModelRef] = []
    for provider, model_id in candidates:
        if not model_id.endswith(FREE_TIER_SUFFIX):
            continue
        ref = ModelRef(id=model_id, provider=provider)
        if exclude is not None and ref == exclude:
            continue
        if ref not in refs:
            refs.append(ref)
    return tuple(refs)
