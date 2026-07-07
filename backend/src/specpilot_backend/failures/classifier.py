from __future__ import annotations

from specpilot_backend.models.verification import (
    FailureCategory,
    FailureClassification,
    VerificationFailure,
)

CATEGORY_PRIORITY: tuple[FailureCategory, ...] = (
    "visual_regression",
    "dom_mismatch_visually_correct",
    "navigation_failure",
    "timing_issue",
    "interaction_failure",
    "state_mismatch",
    "element_not_found",
    "agent_planning_error",
    "unknown",
)


def classify_failure(failure: VerificationFailure) -> FailureClassification:
    """Classify a failed or review-needed verification using deterministic rules."""

    reasons: dict[FailureCategory, str] = {}
    if failure.arbitration_label == "fail_soft":
        reasons["dom_mismatch_visually_correct"] = (
            "Deterministic verification failed while visual verification passed."
        )

    if (
        failure.deterministic_verdict == "pass"
        and failure.vision_verdict == "fail"
        and (failure.vision_confidence or 0.0) >= 0.85
    ) or failure.vision_suggested_failure_type == "visual_regression":
        reasons["visual_regression"] = (
            "DOM evidence passed but high-confidence visual verification failed."
        )

    if _has_navigation_signal(failure):
        reasons["navigation_failure"] = "URL or browser history indicates navigation failure."

    if _has_timing_signal(failure):
        reasons["timing_issue"] = "Trace or visual reasoning indicates unstable loading."

    if _has_element_not_found_signal(failure):
        reasons["element_not_found"] = (
            "Expected visible element was absent from deterministic and visual evidence."
        )

    if _has_interaction_signal(failure):
        reasons["interaction_failure"] = (
            "Agent history indicates an action completed without changing the UI."
        )

    if _has_state_mismatch_signal(failure):
        reasons["state_mismatch"] = (
            "Agent self-report conflicts with final deterministic state."
        )

    if _has_planning_signal(failure):
        reasons["agent_planning_error"] = (
            "Agent history suggests confusion or repeated reverse actions."
        )

    if not reasons:
        reasons["unknown"] = "No strong rule matched the available verification signals."

    primary = _select_primary(reasons)
    secondary: list[FailureCategory] = [
        category for category in reasons if category != primary
    ]
    return FailureClassification(
        primary=primary,
        secondary=secondary,
        primary_reason=reasons[primary],
        deviation_step=1 if primary in {"state_mismatch", "agent_planning_error"} else None,
        raw_signals=failure,
    )


def _select_primary(reasons: dict[FailureCategory, str]) -> FailureCategory:
    for category in CATEGORY_PRIORITY:
        if category in reasons:
            return category
    return "unknown"


def _has_navigation_signal(failure: VerificationFailure) -> bool:
    text = _combined_signal_text(failure)
    return (
        failure.expectation_type == "url_match"
        and failure.deterministic_verdict == "fail"
    ) or any(token in text for token in ("navigation failed", "404", "5xx", "打不开"))


def _has_element_not_found_signal(failure: VerificationFailure) -> bool:
    text = _combined_signal_text(failure)
    both_channels_missing = (
        failure.expectation_type == "element_visible"
        and failure.deterministic_verdict == "fail"
        and failure.vision_verdict in {"fail", None}
    )
    explicit_agent_missing = failure.agent_self_reported_success is False and any(
        token in text
        for token in ("not found", "cannot locate", "找不到", "未发现")
    )
    return both_channels_missing or explicit_agent_missing


def _has_interaction_signal(failure: VerificationFailure) -> bool:
    text = _combined_signal_text(failure)
    return any(
        token in text
        for token in ("no response", "click had no effect", "input had no effect", "无响应")
    ) or (
        failure.expectation_type == "containment"
        and failure.deterministic_verdict == "fail"
        and "drag" in text
    )


def _has_timing_signal(failure: VerificationFailure) -> bool:
    text = _combined_signal_text(failure)
    return any(
        token in text
        for token in ("networkidle", "timeout", "timed out", "loading", "still loading")
    )


def _has_state_mismatch_signal(failure: VerificationFailure) -> bool:
    if failure.agent_self_reported_success is not True:
        return False
    return failure.deterministic_verdict == "fail" or failure.vision_verdict == "fail"


def _has_planning_signal(failure: VerificationFailure) -> bool:
    text = _combined_signal_text(failure)
    return any(
        token in text
        for token in ("confused", "wrong step", "undo", "reverted", "反复", "撤销")
    )


def _combined_signal_text(failure: VerificationFailure) -> str:
    parts = [
        failure.expectation_description,
        failure.deterministic_reason or "",
        failure.vision_reasoning or "",
        failure.vision_evidence or "",
        failure.agent_done_message or "",
        failure.final_url,
        failure.final_dom_summary,
        " ".join(failure.agent_errors),
    ]
    return "\n".join(parts).casefold()
