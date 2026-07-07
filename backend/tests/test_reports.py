import json
from pathlib import Path
from uuid import uuid4

from specpilot_backend.models.events import TraceEvent
from specpilot_backend.models.verification import (
    FailureClassification,
    VerificationFailure,
    VerificationResult,
)
from specpilot_backend.reports.generator import generate_report


def test_report_generator_writes_json_and_html_with_redacted_secrets(
) -> None:
    output_dir = Path(".pytest_cache") / "specpilot-report-tests" / uuid4().hex
    raw_signals = VerificationFailure(
        expectation_id="exp_1",
        expectation_type="text_present",
        expectation_description="The card is visible.",
        deterministic_verdict="fail",
        deterministic_reason="Missing text",
        deterministic_evidence={"expected_text": "Quarterly report"},
        vision_verdict=None,
        vision_confidence=None,
        vision_reasoning=None,
        vision_evidence=None,
        vision_suggested_failure_type=None,
        agent_self_reported_success=True,
        agent_done_message="I completed the task.",
        agent_errors=[],
        final_url="https://demo.4gaboards.com/boards/alpha",
        screenshots=["screenshots/final.jpg"],
        final_dom_summary="No matching card",
        arbitration_label="fail",
    )
    classification = FailureClassification(
        primary="state_mismatch",
        secondary=[],
        primary_reason="Agent self-report conflicts with deterministic evidence.",
        deviation_step=2,
        raw_signals=raw_signals,
    )
    verification_result = VerificationResult(
        expectation_index=0,
        channel="deterministic",
        verdict="fail",
        confidence=1.0,
        reason="Missing text",
        evidence={"expected_text": "Quarterly report", "api_key": "secret-key"},
    )
    trace_event = TraceEvent(
        event_id="evt_1",
        run_id="run_report_001",
        ts="2026-05-06T10:00:00Z",
        type="browser_step",
        node="BrowserUseRun",
        status="done",
        message="Step completed",
        payload={"password": "super-secret", "screenshot": "screenshots/final.jpg"},
    )

    result = generate_report(
        run_summary={
            "run_id": "run_report_001",
            "scenario_id": "sc_001",
            "status": "fail",
            "secret_token": "raw-token",
            "artifacts": {"final_screenshot": "screenshots/final.jpg"},
        },
        verification_results=[verification_result],
        trace_events=[trace_event],
        failure_classification=classification,
        output_dir=output_dir,
    )

    json_path = Path(result["json_path"])
    html_path = Path(result["html_path"])
    assert json_path.is_file()
    assert html_path.is_file()
    assert result["report_id"] == "run_report_001"

    report = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")
    combined = json_path.read_text(encoding="utf-8") + html

    assert report["run"]["run_id"] == "run_report_001"
    assert report["failure_classification"]["primary"] == "state_mismatch"
    assert "report.html" in report["artifact_links"].values()
    assert "secret-key" not in combined
    assert "super-secret" not in combined
    assert "raw-token" not in combined
    assert "[REDACTED]" in combined
