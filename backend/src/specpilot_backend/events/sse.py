from __future__ import annotations

import json
from pathlib import Path

from specpilot_backend.models.events import TraceEvent


def format_sse_event(event: TraceEvent) -> str:
    payload = event.model_dump(mode="json")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.type}\ndata: {data}\n\n"


async def iter_sse_events(
    run_id: str,
    *,
    replay_only: bool = False,
    trace_path: Path | None = None,
):
    from specpilot_backend.events.bus import get_event_bus

    replayed = await get_event_bus().replay(run_id)
    if not replayed and trace_path is not None and trace_path.exists():
        replayed = _read_trace_events(trace_path)

    for event in replayed:
        yield format_sse_event(event).encode("utf-8")
    if replay_only:
        return
    async for event in get_event_bus().subscribe(run_id):
        yield format_sse_event(event).encode("utf-8")


def _read_trace_events(trace_path: Path) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(TraceEvent.model_validate_json(line))
    return events
