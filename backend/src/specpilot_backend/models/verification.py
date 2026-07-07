from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VerificationChannel = Literal["deterministic", "vision"]
VerificationVerdict = Literal["pass", "fail", "needs_review"]
DeterministicVerdict = Literal["pass", "fail"]
VisionVerdict = Literal["pass", "fail", "uncertain"]
ArbitrationLabel = Literal["fail", "fail_soft", "needs_review"]
FailureCategory = Literal[
    "navigation_failure",
    "element_not_found",
    "interaction_failure",
    "timing_issue",
    "state_mismatch",
    "visual_regression",
    "agent_planning_error",
    "dom_mismatch_visually_correct",
    "unknown",
]


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectation_index: int = Field(ge=0)
    channel: VerificationChannel
    verdict: VerificationVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: dict[str, object]


class VerificationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectation_id: str
    expectation_type: str
    expectation_description: str
    deterministic_verdict: DeterministicVerdict | None
    deterministic_reason: str | None
    deterministic_evidence: dict[str, object] | None
    vision_verdict: VisionVerdict | None
    vision_confidence: float | None
    vision_reasoning: str | None
    vision_evidence: str | None
    vision_suggested_failure_type: str | None
    agent_self_reported_success: bool | None
    agent_done_message: str | None
    agent_errors: list[str]
    final_url: str
    screenshots: list[str]
    final_dom_summary: str
    arbitration_label: ArbitrationLabel


class FailureClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: FailureCategory
    secondary: list[FailureCategory]
    primary_reason: str
    deviation_step: int | None
    raw_signals: VerificationFailure
