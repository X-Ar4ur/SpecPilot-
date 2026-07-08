from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from specpilot_backend.models.scenarios import TestScenario


def _scenario(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "scenario_id": "sc1",
        "feature_id": "ft1",
        "title": "t",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/x"],
        "evidence_quotes": ["q"],
        "preconditions": [],
        "test_data": {},
        "steps": [{"order": 1, "action": "a"}],
        "expectations": [],
        "max_steps": 5,
        "requires_visual_check": False,
        "review_status": "auto_validated",
    }
    base.update(overrides)
    return base


def test_data_dependency_defaults_to_none() -> None:
    scenario = TestScenario.model_validate(_scenario())

    assert scenario.data_dependency == "none"
    assert scenario.fixtures == []


def test_fixture_slot_parses_with_defaults() -> None:
    scenario = TestScenario.model_validate(
        _scenario(
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
        )
    )

    slot = scenario.fixtures[0]
    assert slot.ref == "target_card"
    assert slot.kind == "card"
    assert slot.required_attrs == ["title"]
    assert slot.allow_create is True


def test_forbidden_locator_field_inside_fixtures_rejected() -> None:
    with pytest.raises(ValidationError):
        TestScenario.model_validate(
            _scenario(
                fixtures=[{"ref": "r", "kind": "card", "selector": ".x"}],
            )
        )
