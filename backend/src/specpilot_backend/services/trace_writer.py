from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specpilot_backend.models.events import TraceEvent


class TraceWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.run_dir / "trace.jsonl"

    def append(self, event: TraceEvent) -> None:
        payload = event.model_dump(mode="json")
        payload["payload"] = _trace_safe_payload(event.payload)
        with self.trace_path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _trace_safe_payload(payload: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in payload.items():
        if key in {"image_base64", "base64", "screenshot_base64"}:
            continue
        safe[key] = _trace_safe_value(value)
    return safe


def _trace_safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _trace_safe_payload(value)
    if isinstance(value, list):
        return [_trace_safe_value(item) for item in value]
    return value
