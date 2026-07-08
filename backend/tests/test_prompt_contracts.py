from specpilot_backend.config import Settings
from specpilot_backend.llm.deepseek import (
    build_browser_use_deepseek_model,
    build_deepseek_chat_model,
)
from specpilot_backend.prompts.templates import (
    FEATURE_EXTRACTION_PROMPT,
    SCENARIO_GENERATION_PROMPT,
    build_feature_extraction_prompt,
    build_scenario_generation_prompt,
)


def test_feature_prompt_requires_json_and_evidence_constraints() -> None:
    prompt = build_feature_extraction_prompt(
        [
            {
                "source_url": "https://docs.4gaboards.com/docs/user-manual/cards",
                "heading_path": "user-manual / Cards",
                "content": "Users can create cards.",
            }
        ]
    )

    assert FEATURE_EXTRACTION_PROMPT in prompt
    assert '"features"' in prompt
    assert "Return only JSON" in prompt
    assert "Do not invent features" in prompt
    assert "evidence_quotes" in prompt


def test_scenario_prompt_forbids_locator_fields_and_requires_evidence() -> None:
    prompt = build_scenario_generation_prompt(
        feature={
            "feature_id": "ft_card_creation",
            "module": "Card",
            "title": "创建 Card",
            "summary": "用户可以创建 Card。",
            "source_urls": ["https://docs.4gaboards.com/cards/create"],
            "evidence_quotes": ["Click Add Card."],
            "confidence": 0.91,
        },
        evidence_chunks=[
            {
                "source_url": "https://docs.4gaboards.com/cards/create",
                "heading_path": "user-manual / Cards / Create",
                "content": "Click Add Card.",
            }
        ],
    )

    assert SCENARIO_GENERATION_PROMPT in prompt
    assert "Return only JSON" in prompt
    assert "Never output" in prompt
    for forbidden in (
        "selector",
        "locator",
        "xpath",
        "element_id",
        "element_index",
        "css",
        "css_selector",
    ):
        assert forbidden in prompt
    assert "Every scenario must include evidence quotes" in prompt


def test_deepseek_adapter_uses_project_default_model_without_cloud_browser() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-key",
        browser_use_api_key=None,
        deepseek_model="deepseek-v4-pro",
    )
    model = build_deepseek_chat_model(settings=settings)

    assert model.model_name == "deepseek-v4-pro"


def test_browser_use_deepseek_adapter_exposes_browser_use_model_name() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-key",
        browser_use_api_key=None,
        deepseek_model="deepseek-v4-pro",
    )
    model = build_browser_use_deepseek_model(settings=settings)

    assert model.model_name == "deepseek-v4-pro"
    assert model.name == "deepseek-v4-pro"
    assert model.provider == "deepseek"
