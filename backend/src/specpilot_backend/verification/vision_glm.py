from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from specpilot_backend.config import Settings, get_settings
from specpilot_backend.models.verification import VerificationResult, VerificationVerdict

AllowedSuggestedFailure = Literal[
    "visual_regression",
    "state_mismatch",
    "agent_planning_error",
    "dom_mismatch_visually_correct",
]


class GLMVisionThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high: float = Field(default=0.85, ge=0.0, le=1.0)
    low: float = Field(default=0.60, ge=0.0, le=1.0)


class GLMVisionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdict: Literal["pass", "fail", "uncertain", "needs_review"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    reason: str = ""
    evidence: str = ""
    suggested_failure_type: AllowedSuggestedFailure | None = None


class GLMVisionVerifier:
    """Small GLM-4.6V adapter that returns project VerificationResult objects."""

    endpoint = "https://api.z.ai/api/paas/v4/chat/completions"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client

    async def verify(
        self,
        *,
        scenario_title: str,
        expectation_description: str,
        screenshot_initial: bytes | Path,
        screenshot_final: bytes | Path,
        expectation_index: int,
        thresholds: GLMVisionThresholds | None = None,
    ) -> VerificationResult:
        if self.settings.glm_api_key is None:
            return VerificationResult(
                expectation_index=expectation_index,
                channel="vision",
                verdict="needs_review",
                confidence=0.0,
                reason="GLM_API_KEY is not configured.",
                evidence={"glm_model": self.settings.glm_vision_model},
            )

        prompt = build_vision_prompt(
            scenario_title=scenario_title,
            expectation_description=expectation_description,
        )
        payload = {
            "model": self.settings.glm_vision_model,
            "thinking": {"type": "enabled"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        _image_content("initial", screenshot_initial),
                        _image_content("final", screenshot_final),
                    ],
                }
            ],
        }
        headers = {
            "Authorization": (
                "Bearer "
                f"{self.settings.glm_api_key.get_secret_value()}"
            )
        }
        close_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=60)
        try:
            response = await client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover - network path is integration only
            return VerificationResult(
                expectation_index=expectation_index,
                channel="vision",
                verdict="needs_review",
                confidence=0.0,
                reason=f"GLM vision verification failed: {exc.__class__.__name__}",
                evidence={"glm_model": self.settings.glm_vision_model},
            )
        finally:
            if close_client:
                await client.aclose()

        return parse_glm_vision_response(
            content,
            expectation_index=expectation_index,
            thresholds=thresholds
            or GLMVisionThresholds(
                high=self.settings.vision_confidence_high,
                low=self.settings.vision_confidence_low,
            ),
        )


def build_vision_prompt(*, scenario_title: str, expectation_description: str) -> str:
    return (
        "You are a visual verification assistant for a web application UI test.\n"
        f"Scenario title: {scenario_title}\n"
        f"Expectation: {expectation_description}\n\n"
        "The first image is the state before execution. The second image is "
        "the final state after execution.\n"
        "Judge whether the expectation is satisfied using only visible "
        "evidence from those two images. Also note obvious layout overlap, "
        "rendering breakage, or visual regressions.\n"
        "Return strict JSON only, with no markdown fences, using this shape:\n"
        '{"verdict":"pass|fail|uncertain","confidence":0.0,'
        '"reasoning":"1-3 concise sentences","evidence":"specific visual '
        'evidence","suggested_failure_type":"visual_regression|'
        'state_mismatch|agent_planning_error|null"}'
    )


def parse_glm_vision_response(
    raw_response: str,
    *,
    expectation_index: int,
    thresholds: GLMVisionThresholds | None = None,
) -> VerificationResult:
    resolved_thresholds = thresholds or GLMVisionThresholds()
    try:
        data = json.loads(raw_response)
        parsed = GLMVisionResponse.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        return VerificationResult(
            expectation_index=expectation_index,
            channel="vision",
            verdict="needs_review",
            confidence=0.0,
            reason=f"Invalid GLM vision JSON: {exc}",
            evidence={"raw_response": raw_response[:500]},
        )

    reasoning = parsed.reasoning or parsed.reason
    confidence = parsed.confidence
    verdict: VerificationVerdict
    if parsed.verdict in {"uncertain", "needs_review"}:
        verdict = "needs_review"
        reason = reasoning or "GLM vision output was uncertain."
    elif parsed.verdict == "pass" and confidence >= resolved_thresholds.high:
        verdict = "pass"
        reason = reasoning or "GLM vision output met the high confidence threshold."
    elif parsed.verdict == "fail" and confidence >= resolved_thresholds.high:
        verdict = "fail"
        reason = reasoning or "GLM vision output met the high confidence threshold."
    else:
        verdict = "needs_review"
        reason = (
            "GLM vision output had low confidence "
            f"({confidence:.2f}; high={resolved_thresholds.high:.2f}, "
            f"low={resolved_thresholds.low:.2f})."
        )

    return VerificationResult(
        expectation_index=expectation_index,
        channel="vision",
        verdict=verdict,
        confidence=confidence,
        reason=reason,
        evidence={
            "glm_verdict": parsed.verdict,
            "glm_reasoning": reasoning,
            "visual_evidence": parsed.evidence,
            "suggested_failure_type": parsed.suggested_failure_type,
            "threshold_high": resolved_thresholds.high,
            "threshold_low": resolved_thresholds.low,
        },
    )


def _image_content(label: str, image: bytes | Path) -> dict[str, object]:
    image_bytes = image.read_bytes() if isinstance(image, Path) else image
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{encoded}",
            "detail": "high",
        },
        "label": label,
    }
