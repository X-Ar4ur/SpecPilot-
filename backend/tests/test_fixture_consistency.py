from __future__ import annotations

from typing import Any

import pytest

from specpilot_backend.generation.validators import (
    FixtureConsistencyError,
    validate_fixture_consistency,
)
from specpilot_backend.models.scenarios import TestScenario
from specpilot_backend.prompts.templates import SCENARIO_GENERATION_PROMPT


def _payload(**overrides: Any) -> dict[str, Any]:
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
        "is_mutation": False,
        "data_dependency": "none",
        "fixtures": [],
    }
    base.update(overrides)
    return base


def _check(payload: dict[str, Any]) -> None:
    scenario = TestScenario.model_validate(payload)
    validate_fixture_consistency(payload, scenario)


def test_interactive_with_matching_fixtures_passes() -> None:
    _check(
        _payload(
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
            test_data={"card_title": "{{fixture.target_card.title}}"},
        )
    )


def test_interactive_without_fixtures_raises() -> None:
    with pytest.raises(FixtureConsistencyError, match="at least one fixture"):
        _check(_payload(data_dependency="interactive", fixtures=[]))


def test_interactive_token_referencing_undeclared_slot_raises() -> None:
    with pytest.raises(FixtureConsistencyError, match="undeclared"):
        _check(
            _payload(
                data_dependency="interactive",
                fixtures=[{"ref": "target_card", "kind": "card"}],
                test_data={"x": "{{fixture.other_card.title}}"},
            )
        )


def test_non_interactive_with_fixture_token_raises() -> None:
    with pytest.raises(FixtureConsistencyError, match="only allowed in interactive"):
        _check(
            _payload(
                data_dependency="none",
                test_data={"x": "{{fixture.target_card.title}}"},
            )
        )


def test_non_interactive_with_declared_fixtures_raises() -> None:
    with pytest.raises(FixtureConsistencyError, match="only allowed in interactive"):
        _check(
            _payload(
                data_dependency="self_seeding",
                fixtures=[{"ref": "target_card", "kind": "card"}],
            )
        )


def test_self_seeding_without_fixtures_passes() -> None:
    _check(_payload(data_dependency="self_seeding", fixtures=[]))


def test_interactive_allowed_attributes_pass() -> None:
    _check(
        _payload(
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
            test_data={
                "a": "{{fixture.target_card.title}}",
                "b": "{{fixture.target_card.list_name}}",
            },
        )
    )


def test_interactive_unknown_attribute_raises() -> None:
    with pytest.raises(FixtureConsistencyError, match="unsupported attribute"):
        _check(
            _payload(
                data_dependency="interactive",
                fixtures=[{"ref": "target_card", "kind": "card"}],
                test_data={"x": "{{fixture.target_card.assignee}}"},
            )
        )


def test_scenario_prompt_documents_fixtures_and_tokens() -> None:
    assert "data_dependency" in SCENARIO_GENERATION_PROMPT
    assert '"fixtures"' in SCENARIO_GENERATION_PROMPT
    assert "{{fixture." in SCENARIO_GENERATION_PROMPT
    assert "interactive" in SCENARIO_GENERATION_PROMPT
    assert "self_seeding" in SCENARIO_GENERATION_PROMPT
