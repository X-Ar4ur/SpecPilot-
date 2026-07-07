from typing import Literal

from pydantic import BaseModel, ConfigDict

from specpilot_backend.models.verification import VerificationResult

ArbitrationFinalVerdict = Literal["pass", "fail", "needs_review"]
ArbitrationResultLabel = Literal["pass", "fail", "fail_soft", "needs_review"]


class ArbitrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_verdict: ArbitrationFinalVerdict
    label: ArbitrationResultLabel
    reason: str


def arbitrate_expectation(
    *,
    expectation_type: str,
    deterministic_result: VerificationResult | None,
    vision_result: VerificationResult | None,
    requires_visual_check: bool,
    agent_self_reported_success: bool | None = None,
) -> ArbitrationResult:
    """Apply the PLANv2 matrix without trusting agent self-report as a pass."""

    if _is_needs_review(vision_result):
        return ArbitrationResult(
            final_verdict="needs_review",
            label="needs_review",
            reason="VisionVerifier returned low confidence or uncertain evidence.",
        )

    if expectation_type == "semantic":
        if vision_result is None:
            return ArbitrationResult(
                final_verdict="needs_review",
                label="needs_review",
                reason="Semantic expectation requires VisionVerifier.",
            )
        return _single_channel_vision(vision_result)

    if deterministic_result is None:
        return ArbitrationResult(
            final_verdict="needs_review",
            label="needs_review",
            reason="Deterministic verifier did not run.",
        )

    deterministic_verdict = deterministic_result.verdict
    if deterministic_verdict == "needs_review":
        return ArbitrationResult(
            final_verdict="needs_review",
            label="needs_review",
            reason=deterministic_result.reason,
        )

    if not requires_visual_check or vision_result is None:
        if deterministic_verdict == "pass":
            return ArbitrationResult(
                final_verdict="pass",
                label="pass",
                reason="Deterministic verification passed.",
            )
        return ArbitrationResult(
            final_verdict="fail",
            label="fail",
            reason=(
                "Deterministic verification failed; agent self-report is not "
                "a final pass signal."
                if agent_self_reported_success
                else deterministic_result.reason
            ),
        )

    if deterministic_verdict == "pass" and vision_result.verdict == "pass":
        return ArbitrationResult(
            final_verdict="pass",
            label="pass",
            reason="Deterministic and visual verification passed.",
        )
    if deterministic_verdict == "pass" and vision_result.verdict == "fail":
        return ArbitrationResult(
            final_verdict="fail",
            label="fail",
            reason="DOM passed but visual verification failed.",
        )
    if deterministic_verdict == "fail" and vision_result.verdict == "pass":
        return ArbitrationResult(
            final_verdict="needs_review",
            label="fail_soft",
            reason="DOM failed while visual verification passed.",
        )
    return ArbitrationResult(
        final_verdict="fail",
        label="fail",
        reason="Deterministic and visual verification failed.",
    )


def arbitrate_scenario(results: list[ArbitrationResult]) -> ArbitrationFinalVerdict:
    if any(result.final_verdict == "fail" for result in results):
        return "fail"
    if any(result.final_verdict == "needs_review" for result in results):
        return "needs_review"
    return "pass"


def _single_channel_vision(vision_result: VerificationResult) -> ArbitrationResult:
    if vision_result.verdict == "pass":
        return ArbitrationResult(
            final_verdict="pass",
            label="pass",
            reason="Semantic visual verification passed.",
        )
    if vision_result.verdict == "fail":
        return ArbitrationResult(
            final_verdict="fail",
            label="fail",
            reason="Semantic visual verification failed.",
        )
    return ArbitrationResult(
        final_verdict="needs_review",
        label="needs_review",
        reason="Semantic visual verification needs review.",
    )


def _is_needs_review(result: VerificationResult | None) -> bool:
    return result is not None and result.verdict == "needs_review"
