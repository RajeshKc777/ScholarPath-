"""Model registry: identity parsing and deterministic task routing."""

from __future__ import annotations

import pytest

from scholarpath.gateway.base import GatewayNotConfigured
from scholarpath.gateway.registry import (
    ModelEntry,
    ModelRef,
    ModelRegistry,
    parse_model_ref,
)


# -- identity ------------------------------------------------------------------
def test_parse_model_ref_accepts_both_forms() -> None:
    assert parse_model_ref("opencode/gpt-x") == ModelRef(id="gpt-x", provider="opencode")
    assert parse_model_ref("minimax/m3.1") == ModelRef(id="m3.1", provider="minimax")


def test_parse_model_ref_bare_id_gets_default_provider() -> None:
    assert parse_model_ref("  glm-flash ") == ModelRef(id="glm-flash", provider="opencode")


def test_parse_model_ref_empty_means_no_choice() -> None:
    assert parse_model_ref("") is None
    assert parse_model_ref("   ") is None
    assert parse_model_ref(" / ") is None


def test_model_ref_round_trips_as_api_payload() -> None:
    ref = ModelRef(id="m1", provider="p1")
    assert ref.as_api() == {"id": "m1", "providerID": "p1"}
    assert str(ref) == "p1/m1"


# -- catalogue parsing ----------------------------------------------------------
def test_from_api_maps_provider_fields() -> None:
    models = [
        {
            "modelID": "m-free",
            "providerID": "opencode",
            "name": "Free model",
            "enabled": True,
            "capabilities": {"tools": False, "input": ["text"]},
            "limit": {"context": 32000, "output": 4096},
            "cost": [{"input": 0.0, "output": 0.0}],
            "status": "active",
        },
        {
            "modelID": "m-paid",
            "providerID": "anthropic",
            "name": "Paid model",
            "enabled": False,
            "capabilities": {"tools": True, "input": ["text", "image"]},
            "limit": {"context": 200000},
            "cost": [{"input": 3.0, "output": 15.0}],
            "status": "active",
        },
    ]

    registry = ModelRegistry.from_api(models)
    entries = registry.all()

    assert len(entries) == 2
    assert isinstance(entries[0], ModelEntry)
    assert entries[0].id == "m-free"
    assert entries[0].provider == "opencode"
    assert entries[0].context == 32000
    assert entries[0].cost_input == 0.0
    assert entries[0].tools is False
    assert entries[1].enabled is False
    assert entries[1].input_modalities == frozenset({"text", "image"})

    # enabled entries only
    assert registry.select("research") == ModelRef(id="m-free", provider="opencode")


def test_from_api_skips_malformed_rows() -> None:
    registry = ModelRegistry.from_api([None, {"no_id": True}, {"modelID": "ok"}])
    assert [entry.id for entry in registry.all()] == ["ok"]


# -- routing ---------------------------------------------------------------------
def _registry() -> ModelRegistry:
    entries = [
        ModelEntry(id="zz-cheap", provider="p", context=8000, cost_input=0.0),
        ModelEntry(id="aa-big-plain", provider="p", context=128000, cost_input=5.0),
        ModelEntry(
            id="aa-vision",
            provider="p",
            context=64000,
            cost_input=3.0,
            input_modalities=frozenset({"text", "image"}),
        ),
        ModelEntry(
            id="bb-tools",
            provider="p",
            context=96000,
            cost_input=2.0,
            tools=True,
        ),
    ]
    return ModelRegistry(entries)


def test_select_chat_prefers_configured_model_when_enabled() -> None:
    registry = ModelRegistry(_registry().all(), preferred="p/bb-tools")
    assert registry.select("chat") == ModelRef(id="bb-tools", provider="p")


def test_select_chat_falls_back_to_first_enabled_model() -> None:
    assert _registry().select("chat") == ModelRef(id="aa-big-plain", provider="p")


def test_select_chat_ignores_disabled_preference() -> None:
    registry = ModelRegistry(
        [ModelEntry(id="off", provider="p", enabled=False), ModelEntry(id="on", provider="p")],
        preferred="p/off",
    )
    assert registry.select("chat") == ModelRef(id="on", provider="p")


def test_select_classify_takes_cheapest() -> None:
    assert _registry().select("classify") == ModelRef(id="zz-cheap", provider="p")


def test_select_extract_prefers_vision_then_context() -> None:
    assert _registry().select("extract") == ModelRef(id="aa-vision", provider="p")


def test_select_research_prefers_tools_then_context() -> None:
    assert _registry().select("research") == ModelRef(id="bb-tools", provider="p")


def test_select_unknown_task_is_an_error() -> None:
    with pytest.raises(ValueError):
        _registry().select("translate")


def test_select_with_no_enabled_models_raises_not_configured() -> None:
    registry = ModelRegistry([ModelEntry(id="off", provider="p", enabled=False)])
    with pytest.raises(GatewayNotConfigured):
        registry.select("chat")


def test_selection_is_deterministic_for_equal_candidates() -> None:
    entries = [
        ModelEntry(id="b", provider="p", context=8000),
        ModelEntry(id="a", provider="p", context=8000),
    ]
    assert ModelRegistry(entries).select("chat") == ModelRef(id="a", provider="p")
