from __future__ import annotations

from typing import Any

from specpilot_backend.generation.validators import validate_scenario_payload
from specpilot_backend.ingestion.chunker import ManualChunk
from specpilot_backend.services.manual_pipeline import _ScenarioItem


def _interactive_llm_scenario() -> dict[str, Any]:
    # Shape an LLM would emit for an interactive scenario per the prompt.
    return {
        "scenario_id": "sc_open_card_001",
        "feature_id": "ft_card_open",
        "title": "从 List View 打开对应 Card",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/cards/open"],
        "evidence_quotes": ["打开 Card"],
        "preconditions": ["List View 中存在一张可识别标题的 Card"],
        "test_data": {"card_title": "{{fixture.target_card.title}}"},
        "steps": [
            {"order": 1, "action": "打开标题为 {{fixture.target_card.title}} 的 Card"}
        ],
        "expectations": [
            {
                "type": "element_visible",
                "description": "Card 详情显示标题",
                "params": {"text": "{{fixture.target_card.title}}"},
            }
        ],
        "max_steps": 6,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "data_dependency": "interactive",
        "fixtures": [{"ref": "target_card", "kind": "card"}],
    }


def test_scenario_item_preserves_data_dependency_and_fixtures() -> None:
    item = _ScenarioItem.model_validate(_interactive_llm_scenario())
    payload = item.model_dump()

    assert payload["data_dependency"] == "interactive"
    assert payload["fixtures"] == [{"ref": "target_card", "kind": "card"}]


def test_interactive_llm_scenario_passes_validation() -> None:
    # Regression: before fixtures/data_dependency were carried through
    # _ScenarioItem, the surviving tokens made this fail fixture consistency.
    item = _ScenarioItem.model_validate(_interactive_llm_scenario())
    payload = item.model_dump()
    payload["feature_id"] = "ft_card_open"
    chunks = [ManualChunk(content="打开 Card", metadata={})]

    scenario = validate_scenario_payload(payload, chunks)

    assert scenario.data_dependency == "interactive"
    assert scenario.fixtures[0].ref == "target_card"
