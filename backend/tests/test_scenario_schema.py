import pytest
from pydantic import ValidationError

from specpilot_backend.models.events import TraceEvent
from specpilot_backend.models.features import Feature
from specpilot_backend.models.mutations import MutatedScenario
from specpilot_backend.models.runs import Run
from specpilot_backend.models.scenarios import TestScenario as ScenarioModel
from specpilot_backend.models.verification import (
    FailureClassification,
    VerificationFailure,
    VerificationResult,
)


def valid_scenario_payload() -> dict[str, object]:
    return {
        "scenario_id": "sc_create_card_001",
        "feature_id": "ft_card_creation",
        "title": "在指定 List 中创建新 Card",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/cards/create"],
        "evidence_quotes": ["Click Add Card to create a new card."],
        "preconditions": ["用户已进入一个 Board"],
        "test_data": {"card_title": "完成季度报告"},
        "steps": [{"order": 1, "action": "在目标 List 中打开添加 Card 的入口"}],
        "expectations": [
            {
                "type": "element_visible",
                "description": "新建 Card 标题在目标 List 中可见",
                "params": {"text": "完成季度报告", "container_text": "To Do"},
            }
        ],
        "max_steps": 10,
        "requires_visual_check": False,
        "review_status": "auto_validated",
    }


def test_valid_scenario_passes_schema() -> None:
    scenario = ScenarioModel.model_validate(valid_scenario_payload())

    assert scenario.scenario_id == "sc_create_card_001"
    assert scenario.steps[0].action == "在目标 List 中打开添加 Card 的入口"
    assert scenario.is_mutation is False


@pytest.mark.parametrize(
    "field_name",
    ["selector", "locator", "xpath", "element_id", "element_index", "css_selector"],
)
def test_scenario_rejects_nested_forbidden_locator_fields(field_name: str) -> None:
    payload = valid_scenario_payload()
    payload["test_data"] = {
        "safe_value": "To Do",
        "nested": [{"label": "bad", field_name: "#app .card"}],
    }

    with pytest.raises(ValidationError, match=field_name):
        ScenarioModel.model_validate(payload)


def test_scenario_rejects_css_field_anywhere() -> None:
    payload = valid_scenario_payload()
    payload["expectations"] = [
        {
            "type": "text_present",
            "description": "页面出现目标文本",
            "params": {"text": "完成季度报告", "css": ".card-title"},
        }
    ]

    with pytest.raises(ValidationError, match="css"):
        ScenarioModel.model_validate(payload)


def test_feature_requires_source_urls_and_evidence_quotes() -> None:
    with pytest.raises(ValidationError):
        Feature.model_validate(
            {
                "feature_id": "ft_card_creation",
                "module": "Card",
                "title": "创建 Card",
                "summary": "用户可以创建 Card。",
                "source_urls": [],
                "evidence_quotes": ["Click Add Card to create a new card."],
                "confidence": 0.91,
                "coverage_status": "covered",
            }
        )

    with pytest.raises(ValidationError):
        Feature.model_validate(
            {
                "feature_id": "ft_card_creation",
                "module": "Card",
                "title": "创建 Card",
                "summary": "用户可以创建 Card。",
                "source_urls": ["https://docs.4gaboards.com/cards/create"],
                "evidence_quotes": [],
                "confidence": 0.91,
                "coverage_status": "covered",
            }
        )


def test_feature_quote_validator_rejects_absent_source_chunk_quotes() -> None:
    feature = Feature.model_validate(
        {
            "feature_id": "ft_card_creation",
            "module": "Card",
            "title": "创建 Card",
            "summary": "用户可以创建 Card。",
            "source_urls": ["https://docs.4gaboards.com/cards/create"],
            "evidence_quotes": ["Click Add Card to create a new card."],
            "confidence": 0.91,
            "coverage_status": "covered",
        }
    )

    assert feature.evidence_quotes_are_supported(
        ["The Card can be created by using Add Card."]
    ) is False
    assert feature.evidence_quotes_are_supported(
        ["Click Add Card to create a new card."]
    ) is True


def test_mutated_scenario_extends_test_scenario_contract() -> None:
    payload = valid_scenario_payload()
    payload.update(
        {
            "scenario_id": "sc_mut_create_card_empty_title",
            "is_mutation": True,
            "mutation_id": "mut_empty_card_title",
            "source_scenario_id": "sc_create_card_001",
            "mutation_type": "data",
            "mutation_description": "将 card_title 替换为空字符串",
            "mutation_params": {"field": "card_title", "value": ""},
            "expected_detection": True,
            "detection_outcome": None,
        }
    )

    mutation = MutatedScenario.model_validate(payload)

    assert mutation.is_mutation is True
    assert mutation.expected_detection is True


def test_run_trace_and_verification_contracts_validate() -> None:
    run = Run.model_validate(
        {
            "run_id": "run_20260506_001",
            "scenario_ids": ["sc_create_card_001"],
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "verdict": None,
            "failure_primary": None,
            "failure_secondary": [],
            "artifact_dir": "data/runs/run_20260506_001",
            "report_id": None,
        }
    )
    event = TraceEvent.model_validate(
        {
            "event_id": "evt_001",
            "run_id": run.run_id,
            "ts": "2026-05-06T00:00:00Z",
            "type": "node_status",
            "node": "ScenarioLoader",
            "status": "running",
            "message": "加载场景",
            "payload": {},
        }
    )
    result = VerificationResult.model_validate(
        {
            "expectation_index": 0,
            "channel": "deterministic",
            "verdict": "pass",
            "confidence": 1.0,
            "reason": "文本可见",
            "evidence": {"text": "完成季度报告"},
        }
    )

    assert event.run_id == run.run_id
    assert result.verdict == "pass"


def test_failure_classification_keeps_raw_unmerged_signals() -> None:
    failure = VerificationFailure.model_validate(
        {
            "expectation_id": "exp_001",
            "expectation_type": "element_visible",
            "expectation_description": "Card 标题可见",
            "deterministic_verdict": "fail",
            "deterministic_reason": "文本不存在",
            "deterministic_evidence": {"text": "完成季度报告"},
            "vision_verdict": None,
            "vision_confidence": None,
            "vision_reasoning": None,
            "vision_evidence": None,
            "vision_suggested_failure_type": None,
            "agent_self_reported_success": False,
            "agent_done_message": "无法找到 Add Card",
            "agent_errors": [],
            "final_url": "https://demo.4gaboards.com/",
            "screenshots": [],
            "final_dom_summary": "No card title",
            "arbitration_label": "fail",
        }
    )
    classification = FailureClassification.model_validate(
        {
            "primary": "element_not_found",
            "secondary": ["agent_planning_error"],
            "primary_reason": "Agent 未找到目标入口。",
            "deviation_step": None,
            "raw_signals": failure,
        }
    )

    assert classification.raw_signals.deterministic_verdict == "fail"
