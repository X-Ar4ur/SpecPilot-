import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from specpilot_backend.events.bus import InMemoryRunEventBus
from specpilot_backend.events.sse import format_sse_event, iter_sse_events
from specpilot_backend.models.events import TraceEvent
from specpilot_backend.services.trace_writer import TraceWriter


def make_event(**payload: object) -> TraceEvent:
    return TraceEvent(
        event_id="evt_001",
        run_id="run_001",
        ts="2026-05-06T00:00:00+00:00",
        type="browser_step",
        node="BrowserUseRun",
        status="running",
        message="step 1",
        payload=dict(payload),
    )


def test_trace_writer_appends_json_lines_and_removes_base64_frames() -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-trace-tests" / uuid4().hex
    writer = TraceWriter(tmp_path)
    event = make_event(image_base64="raw-frame", screenshot_path="screenshots/1.png")

    writer.append(event)

    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event_id"] == "evt_001"
    assert parsed["payload"] == {"screenshot_path": "screenshots/1.png"}


def test_sse_formatter_uses_trace_event_schema() -> None:
    event = make_event(action="click")
    formatted = format_sse_event(event)

    assert formatted.startswith("event: browser_step\n")
    assert '"event_id":"evt_001"' in formatted
    assert '"action":"click"' in formatted
    assert formatted.endswith("\n\n")


@pytest.mark.anyio
async def test_sse_replays_trace_file_when_memory_bus_is_empty() -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-sse-replay-tests" / uuid4().hex
    writer = TraceWriter(tmp_path)
    writer.append(make_event(action="click"))

    chunks = []
    async for chunk in iter_sse_events(
        "run_001",
        replay_only=True,
        trace_path=tmp_path / "trace.jsonl",
    ):
        chunks.append(chunk.decode("utf-8"))

    assert len(chunks) == 1
    assert '"event_id":"evt_001"' in chunks[0]
    assert '"action":"click"' in chunks[0]


@pytest.mark.anyio
async def test_run_event_bus_replays_published_events() -> None:
    bus = InMemoryRunEventBus()
    event = make_event(action="navigate")

    await bus.publish(event)

    events = await bus.replay("run_001")
    assert events == [event]


@pytest.mark.anyio
async def test_run_event_bus_subscription_receives_future_event() -> None:
    bus = InMemoryRunEventBus()
    event = make_event(action="input")

    async def receive_one() -> TraceEvent:
        async for received in bus.subscribe("run_001"):
            return received
        raise AssertionError("subscription ended")

    task = asyncio.create_task(receive_one())
    await bus.publish(event)

    assert await asyncio.wait_for(task, timeout=1) == event
