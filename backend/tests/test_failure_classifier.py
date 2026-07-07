from specpilot_backend.failures.classifier import classify_failure
from specpilot_backend.models.verification import VerificationFailure


def failure(**overrides: object) -> VerificationFailure:
    data: dict[str, object] = {
        "expectation_id": "exp_1",
        "expectation_type": "element_visible",
        "expectation_description": "The Add card button is visible.",
        "deterministic_verdict": "fail",
        "deterministic_reason": "Missing text",
        "deterministic_evidence": {"expected_text": "Add card"},
        "vision_verdict": "fail",
        "vision_confidence": 0.91,
        "vision_reasoning": "The button is not visible.",
        "vision_evidence": "No Add card button appears.",
        "vision_suggested_failure_type": None,
        "agent_self_reported_success": False,
        "agent_done_message": None,
        "agent_errors": [],
        "final_url": "https://demo.4gaboards.com/boards/alpha",
        "screenshots": ["screenshots/final.jpg"],
        "final_dom_summary": "Board Alpha without Add card",
        "arbitration_label": "fail",
    }
    data.update(overrides)
    return VerificationFailure.model_validate(data)


def test_classifier_prioritizes_arbitration_categories() -> None:
    dom_mismatch = classify_failure(
        failure(arbitration_label="fail_soft", vision_verdict="pass")
    )
    visual_regression = classify_failure(
        failure(
            expectation_type="text_present",
            deterministic_verdict="pass",
            vision_verdict="fail",
            vision_confidence=0.92,
            vision_suggested_failure_type="visual_regression",
        )
    )

    assert dom_mismatch.primary == "dom_mismatch_visually_correct"
    assert visual_regression.primary == "visual_regression"


def test_classifier_detects_navigation_and_element_failures() -> None:
    navigation = classify_failure(
        failure(
            expectation_type="url_match",
            deterministic_verdict="fail",
            agent_errors=["GET /missing returned 404"],
            final_url="https://demo.4gaboards.com/missing",
        )
    )
    element = classify_failure(failure())

    assert navigation.primary == "navigation_failure"
    assert element.primary == "element_not_found"


def test_classifier_detects_interaction_and_timing_failures() -> None:
    interaction = classify_failure(
        failure(agent_done_message="Clicked Save, but the page had no response.")
    )
    timing = classify_failure(
        failure(
            agent_errors=["Timed out waiting for networkidle"],
            vision_reasoning="The page still appears to be loading.",
        )
    )

    assert interaction.primary == "interaction_failure"
    assert timing.primary == "timing_issue"


def test_classifier_uses_agent_success_as_state_mismatch_signal_not_pass() -> None:
    classification = classify_failure(
        failure(
            expectation_type="containment",
            deterministic_verdict="fail",
            vision_verdict=None,
            vision_confidence=None,
            vision_reasoning=None,
            vision_evidence=None,
            agent_self_reported_success=True,
            final_dom_summary="Quarterly report exists, but it is in Done not To Do.",
        )
    )

    assert classification.primary == "state_mismatch"
    assert classification.raw_signals.agent_self_reported_success is True


def test_classifier_falls_back_to_unknown() -> None:
    classification = classify_failure(
        failure(
            expectation_type="semantic",
            deterministic_verdict=None,
            deterministic_reason=None,
            deterministic_evidence=None,
            vision_verdict="uncertain",
            vision_confidence=0.42,
            vision_reasoning="The screenshot is ambiguous.",
            vision_evidence="A modal covers the board.",
            final_dom_summary="Ambiguous state",
            arbitration_label="needs_review",
        )
    )

    assert classification.primary == "unknown"
