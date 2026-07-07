from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

from specpilot_backend.models.events import TraceEvent
from specpilot_backend.models.verification import (
    FailureClassification,
    VerificationResult,
)

SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "credential",
    "authorization",
)
REDACTED = "[REDACTED]"


def generate_report(
    *,
    run_summary: dict[str, object],
    verification_results: list[VerificationResult],
    trace_events: Sequence[TraceEvent | dict[str, object]],
    failure_classification: FailureClassification | None,
    output_dir: Path,
) -> dict[str, str]:
    """Write redacted JSON and HTML run reports."""

    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(run_summary.get("run_id", "run"))
    report = _redact(
        {
            "run": run_summary,
            "verification_results": [
                result.model_dump(mode="json") for result in verification_results
            ],
            "trace_events": [_dump_model(event) for event in trace_events],
            "failure_classification": (
                failure_classification.model_dump(mode="json")
                if failure_classification is not None
                else None
            ),
            "artifact_links": {
                "report_json": "report.json",
                "report_html": "report.html",
                "trace": "trace.jsonl",
                "screenshots": "screenshots/",
                "verification": "verification/",
            },
        }
    )

    json_path = output_dir / "report.json"
    html_path = output_dir / "report.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    html_path.write_text(_render_html_report(report), encoding="utf-8")
    return {
        "report_id": run_id,
        "json_path": str(json_path),
        "html_path": str(html_path),
    }


def _dump_model(value: BaseModel | dict[str, object]) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _redact(value: Any, *, key_name: str | None = None) -> Any:
    if key_name is not None and _is_secret_key(key_name):
        return REDACTED
    if isinstance(value, dict):
        return {str(key): _redact(nested, key_name=str(key)) for key, nested in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _is_secret_key(key_name: str) -> bool:
    lowered = key_name.casefold()
    return any(part in lowered for part in SECRET_KEY_PARTS)


def _render_html_report(report: dict[str, object]) -> str:
    run = report.get("run", {})
    classification = report.get("failure_classification")
    verification_results = report.get("verification_results", [])
    trace_events = report.get("trace_events", [])
    artifact_links = report.get("artifact_links", {})
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>SpecPilot Run Report</title>",
            "<style>",
            "body{font-family:Arial,sans-serif;margin:24px;color:#17202a}",
            "code,pre{background:#f4f6f8;padding:8px;border-radius:6px}",
            "section{margin-bottom:24px}",
            "</style>",
            "</head>",
            "<body>",
            "<h1>SpecPilot Run Report</h1>",
            _section("Run Summary", run),
            _section("Verification Results", verification_results),
            _section("Failure Classification", classification),
            _section("Trace Events", trace_events),
            _section("Artifact Links", artifact_links),
            "</body>",
            "</html>",
        ]
    )


def _section(title: str, value: object) -> str:
    payload = html.escape(json.dumps(value, ensure_ascii=False, indent=2))
    return f"<section><h2>{html.escape(title)}</h2><pre>{payload}</pre></section>"
