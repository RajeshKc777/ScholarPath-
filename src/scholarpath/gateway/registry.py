"""Model registry and task-based routing.

The registry holds what a provider actually advertises (identity, capabilities,
cost, limits) and chooses a model for a task. Routing is driven by task
requirements - never by arbitrary switching - and every selection is
deterministic for a given registry state.

Milestone 2 uses this for chat selection; later milestones add classify,
research and extract tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scholarpath.gateway.base import GatewayNotConfigured

DEFAULT_PROVIDER = "opencode"
KNOWN_TASKS = ("chat", "classify", "research", "extract")


@dataclass(frozen=True, slots=True)
class ModelRef:
    """A fully qualified model identity."""

    id: str
    provider: str = DEFAULT_PROVIDER

    def as_api(self) -> dict[str, str]:
        return {"id": self.id, "providerID": self.provider}

    def __str__(self) -> str:
        return f"{self.provider}/{self.id}"


def parse_model_ref(text: str, default_provider: str = DEFAULT_PROVIDER) -> ModelRef | None:
    """Parse ``provider/model`` or a bare model id. Empty text means "no choice"."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    if "/" in cleaned:
        provider, model_id = cleaned.split("/", 1)
        provider = provider.strip()
        model_id = model_id.strip()
        if provider and model_id:
            return ModelRef(id=model_id, provider=provider)
        return None
    return ModelRef(id=cleaned, provider=default_provider)


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """One model as advertised by the registry source."""

    id: str
    provider: str = DEFAULT_PROVIDER
    name: str = ""
    enabled: bool = True
    tools: bool = False
    context: int = 0
    input_modalities: frozenset[str] = field(default_factory=lambda: frozenset({"text"}))
    cost_input: float = 0.0
    status: str = "active"

    @property
    def ref(self) -> ModelRef:
        return ModelRef(id=self.id, provider=self.provider)


class ModelRegistry:
    """Deterministic, task-aware model selection."""

    def __init__(
        self,
        entries: list[ModelEntry],
        preferred: str | None = None,
    ) -> None:
        self._entries = tuple(entries)
        self._preferred = parse_model_ref(preferred or "")

    @classmethod
    def from_api(cls, models: list[dict], preferred: str | None = None) -> ModelRegistry:
        entries: list[ModelEntry] = []
        for item in models:
            if not isinstance(item, dict) or not item.get("modelID"):
                continue
            capabilities = item.get("capabilities") or {}
            costs = item.get("cost") or []
            first_cost = costs[0] if costs and isinstance(costs[0], dict) else {}
            limit = item.get("limit") or {}
            entries.append(
                ModelEntry(
                    id=str(item["modelID"]),
                    provider=str(item.get("providerID") or DEFAULT_PROVIDER),
                    name=str(item.get("name") or ""),
                    enabled=bool(item.get("enabled", True)),
                    tools=bool(capabilities.get("tools", False)),
                    context=int(limit.get("context") or 0),
                    input_modalities=frozenset(capabilities.get("input") or ["text"]),
                    cost_input=float(first_cost.get("input") or 0.0),
                    status=str(item.get("status") or "active"),
                )
            )
        return cls(entries, preferred=preferred)

    @classmethod
    def from_ids(cls, model_ids: list[str], provider: str = DEFAULT_PROVIDER) -> ModelRegistry:
        """Fallback registry when the provider cannot be queried."""
        return cls([ModelEntry(id=model_id, provider=provider) for model_id in model_ids])

    def all(self) -> tuple[ModelEntry, ...]:
        return self._entries

    def select(self, task: str, preferred: str | None = None) -> ModelRef:
        """Return the best enabled model for a task.

        Rules (deterministic, ties broken by model id):
        - chat:     explicit preference first, then the first enabled model;
        - classify: cheapest, then smallest context (classification is cheap work);
        - extract:  vision-capable first, then largest context;
        - research: tool-capable first, then largest context.
        """
        candidates = [entry for entry in self._entries if entry.enabled]
        if not candidates:
            raise GatewayNotConfigured(
                "No enabled models are available. Check the provider configuration."
            )

        choice = parse_model_ref(preferred or "") or self._preferred
        if task == "chat":
            if choice is not None:
                match = self._find(choice, candidates)
                if match is not None:
                    return match.ref
            return sorted(candidates, key=lambda entry: entry.id)[0].ref

        if task == "classify":
            return min(
                candidates, key=lambda entry: (entry.cost_input, entry.context, entry.id)
            ).ref

        if task == "extract":
            vision = [entry for entry in candidates if "image" in entry.input_modalities]
            pool = vision or candidates
            return max(pool, key=lambda entry: (entry.context, entry.id)).ref

        if task == "research":
            tooled = [entry for entry in candidates if entry.tools]
            pool = tooled or candidates
            return max(pool, key=lambda entry: (entry.context, entry.id)).ref

        raise ValueError(
            f"Unknown routing task {task!r}; expected one of {', '.join(KNOWN_TASKS)}."
        )

    @staticmethod
    def _find(ref: ModelRef, candidates: list[ModelEntry]) -> ModelEntry | None:
        for entry in candidates:
            if entry.id == ref.id and entry.provider == ref.provider:
                return entry
        return None
