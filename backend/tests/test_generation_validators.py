import pytest

from specpilot_backend.generation.features import generate_feature_payloads
from specpilot_backend.generation.scenarios import generate_scenario_payloads
from specpilot_backend.generation.validators import (
    EvidenceValidationError,
    ZeroLocatorValidationError,
    validate_feature_payload,
    validate_evidence_quotes,
    validate_zero_locator_payload,
)
from specpilot_backend.ingestion.chunker import ManualChunk


def manual_chunk() -> ManualChunk:
    return ManualChunk(
        content=(
            "Users can create a card from a list by clicking Add card, entering "
            "a title, and confirming the creation."
        ),
        metadata={
            "source_url": "https://docs.4gaboards.com/docs/user-manual/cards#create-card",
            "page_url": "https://docs.4gaboards.com/docs/user-manual/cards",
            "page_title": "Cards",
            "heading_path": "user-manual / Cards / Create card",
            "manual_section": "user-manual",
            "module": "Card",
            "language": "en",
            "is_ui_operational": True,
            "content_hash": "sha256:test",
        },
    )


def test_quote_validator_rejects_quotes_absent_from_source_chunks() -> None:
    validate_evidence_quotes(["clicking Add card"], [manual_chunk()])

    with pytest.raises(EvidenceValidationError, match="not present"):
        validate_evidence_quotes(["drag a card between lists"], [manual_chunk()])


def test_zero_locator_validator_rejects_forbidden_nested_fields() -> None:
    payload = {
        "steps": [{"order": 1, "action": "创建 Card"}],
        "expectations": [{"params": {"css_selector": ".card-title"}}],
    }

    with pytest.raises(ZeroLocatorValidationError, match="css_selector"):
        validate_zero_locator_payload(payload)


def test_feature_generation_is_evidence_grounded_and_persistable() -> None:
    features = generate_feature_payloads([manual_chunk()])

    assert features == [
        {
            "feature_id": "ft_card_create_card",
            "module": "Card",
            "title": "Create card",
            "summary": "Users can create a card from a list.",
            "source_urls": [
                "https://docs.4gaboards.com/docs/user-manual/cards#create-card"
            ],
            "evidence_quotes": ["Users can create a card from a list"],
            "confidence": 0.75,
            "coverage_status": "uncovered",
        }
    ]


def test_feature_validator_normalizes_llm_specific_module_labels() -> None:
    chunk = ManualChunk(
        content="4ga Boards features a comprehensive notifications system.",
        metadata={
            "source_url": "https://docs.4gaboards.com/docs/notifications",
            "page_url": "https://docs.4gaboards.com/docs/notifications",
            "page_title": "Notifications",
            "heading_path": "user-manual / Notifications",
            "manual_section": "user-manual",
            "module": "Other",
            "language": "en",
            "is_ui_operational": True,
            "content_hash": "sha256:notifications",
        },
    )
    payload = {
        "feature_id": "ft_notifications_center",
        "module": "Notifications",
        "title": "Notification Center",
        "summary": "Users can inspect notifications.",
        "source_urls": [chunk.metadata["source_url"]],
        "evidence_quotes": ["4ga Boards features a comprehensive notifications system"],
        "confidence": 0.81,
        "coverage_status": "covered",
    }

    feature = validate_feature_payload(payload, [chunk])

    assert feature.module == "Other"
    assert payload["module"] == "Other"


def test_scenario_generation_returns_valid_zero_locator_payloads() -> None:
    feature = generate_feature_payloads([manual_chunk()])[0]
    scenarios = generate_scenario_payloads([feature], {feature["feature_id"]: [manual_chunk()]})

    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario["scenario_id"] == "sc_card_create_card_001"
    assert scenario["feature_id"] == feature["feature_id"]
    assert scenario["source_urls"] == feature["source_urls"]
    assert scenario["evidence_quotes"] == feature["evidence_quotes"]
    assert scenario["priority"] == "P1"
    assert scenario["difficulty"] == "simple"
    assert scenario["max_steps"] == 20
    assert scenario["requires_visual_check"] is False
    assert scenario["review_status"] == "auto_validated"
    assert scenario["steps"] == [
        {"order": 1, "action": "打开包含目标 List 的 Board"},
        {"order": 2, "action": "在目标 List 中打开添加 Card 的入口"},
        {"order": 3, "action": "输入测试 Card 标题并确认创建"},
    ]
    assert scenario["expectations"][0]["type"] == "element_visible"
    validate_zero_locator_payload(scenario)
