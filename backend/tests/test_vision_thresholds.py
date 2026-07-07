from specpilot_backend.verification.vision_glm import (
    GLMVisionThresholds,
    build_vision_prompt,
    parse_glm_vision_response,
)


def test_glm_parser_accepts_high_confidence_pass() -> None:
    result = parse_glm_vision_response(
        '{"verdict": "pass", "confidence": 0.91, '
        '"reasoning": "The final screenshot shows the expected card.", '
        '"evidence": "A card titled Quarterly report is visible.", '
        '"suggested_failure_type": null}',
        expectation_index=0,
        thresholds=GLMVisionThresholds(high=0.85, low=0.60),
    )

    assert result.channel == "vision"
    assert result.verdict == "pass"
    assert result.confidence == 0.91
    assert result.evidence["glm_verdict"] == "pass"


def test_glm_parser_marks_mid_confidence_as_needs_review() -> None:
    result = parse_glm_vision_response(
        '{"verdict": "pass", "confidence": 0.70, '
        '"reasoning": "The card may be present.", '
        '"evidence": "Text is partially visible.", '
        '"suggested_failure_type": null}',
        expectation_index=1,
        thresholds=GLMVisionThresholds(high=0.85, low=0.60),
    )

    assert result.verdict == "needs_review"
    assert "low confidence" in result.reason.lower()


def test_glm_parser_accepts_high_confidence_fail() -> None:
    result = parse_glm_vision_response(
        '{"verdict": "fail", "confidence": 0.93, '
        '"reasoning": "The target card is absent.", '
        '"evidence": "No matching title appears.", '
        '"suggested_failure_type": "state_mismatch"}',
        expectation_index=2,
        thresholds=GLMVisionThresholds(high=0.85, low=0.60),
    )

    assert result.verdict == "fail"
    assert result.evidence["suggested_failure_type"] == "state_mismatch"


def test_glm_parser_rejects_invalid_or_uncertain_output_as_needs_review() -> None:
    invalid = parse_glm_vision_response(
        "not json",
        expectation_index=3,
        thresholds=GLMVisionThresholds(high=0.85, low=0.60),
    )
    uncertain = parse_glm_vision_response(
        '{"verdict": "uncertain", "confidence": 0.99, '
        '"reasoning": "Ambiguous screenshot.", '
        '"evidence": "The UI is hidden by a modal.", '
        '"suggested_failure_type": null}',
        expectation_index=4,
        thresholds=GLMVisionThresholds(high=0.85, low=0.60),
    )

    assert invalid.verdict == "needs_review"
    assert "Invalid GLM vision JSON" in invalid.reason
    assert uncertain.verdict == "needs_review"


def test_vision_prompt_requires_structured_json_without_secrets() -> None:
    prompt = build_vision_prompt(
        scenario_title="Create card",
        expectation_description="A new card appears in To Do.",
    )

    assert "GLM_API_KEY" not in prompt
    assert "JSON" in prompt
    assert "verdict" in prompt
    assert "confidence" in prompt
