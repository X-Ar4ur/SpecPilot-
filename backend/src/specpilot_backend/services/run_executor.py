from __future__ import annotations

import shutil
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from specpilot_backend.agent.browser_use_runner import (
    BrowserUseRunResult,
    run_scenario_with_browser_use,
)
from specpilot_backend.config import Settings, get_settings
from specpilot_backend.events.bus import get_event_bus
from specpilot_backend.fixtures.binding_service import (
    FixturePreconditionError,
    resolve_scenario_fixtures,
)
from specpilot_backend.ids import new_event_id
from specpilot_backend.models.events import TraceEvent, TraceEventType
from specpilot_backend.models.scenarios import TestScenario
from specpilot_backend.reports.generator import generate_report
from specpilot_backend.services.persistence import (
    get_run_payload,
    get_scenario_payload,
    save_run_payload,
    update_scenario_latest_result,
)
from specpilot_backend.services.trace_writer import TraceWriter

BrowserUseRunner = Callable[..., Awaitable[BrowserUseRunResult]]
_ACTIVE_RUN_IDS: set[str] = set()


def active_run_ids() -> set[str]:
    return set(_ACTIVE_RUN_IDS)


async def execute_run(
    run_id: str,
    *,
    settings: Settings | None = None,
    runner: BrowserUseRunner = run_scenario_with_browser_use,
) -> None:
    resolved_settings = settings or get_settings()
    run = get_run_payload(run_id)
    if run is None:
        return

    _ACTIVE_RUN_IDS.add(run_id)
    run_dir = Path(str(run["artifact_dir"]))
    writer = TraceWriter(run_dir)
    trace_events: list[TraceEvent] = []
    started_at = _utc_now()
    run = _update_run(
        run,
        status="running",
        started_at=started_at,
        verdict=None,
    )
    save_run_payload(run)

    try:
        await _publish(
            _event(run_id, "node_status", "ScenarioLoader", "running", "加载测试场景"),
            writer,
            trace_events,
        )
        scenario_payload = _first_scenario_payload(run)
        await _publish(
            _event(run_id, "node_status", "ScenarioLoader", "success", "测试场景已加载"),
            writer,
            trace_events,
        )
        await _publish(
            _event(
                run_id, "node_status", "FixtureResolver", "running", "解析前置数据绑定"
            ),
            writer,
            trace_events,
        )
        scenario_payload = resolve_scenario_fixtures(
            scenario_payload, settings=resolved_settings
        )
        scenario = TestScenario.model_validate(scenario_payload)
        await _publish(
            _event(
                run_id, "node_status", "FixtureResolver", "success", "前置数据已就绪"
            ),
            writer,
            trace_events,
        )

        await _publish(
            _event(
                run_id,
                "node_status",
                "BrowserUseRun",
                "running",
                "browser-use 执行已启动",
            ),
            writer,
            trace_events,
        )
        with _BrowserUseLogCapture(
            run_id=run_id,
            run_dir=run_dir,
            writer=writer,
            trace_events=trace_events,
            settings=resolved_settings,
        ):
            result = await _run_browser_use_runner(
                runner,
                scenario,
                run_id=run_id,
                settings=resolved_settings,
                publish_history_events=False,
            )
        await _publish_browser_use_result(run_id, result, run_dir, writer, trace_events)
        verdict = "pass" if result.success is True else "fail"
        await _publish(
            _event(
                run_id,
                "node_status",
                "BrowserUseRun",
                "success" if verdict == "pass" else "failed",
                result.final_result or "browser-use 执行结束",
            ),
            writer,
            trace_events,
        )

        for node in (
            "TraceCollector",
            "DeterministicVerifier",
            "FailureClassifier",
            "Reporter",
        ):
            await _publish(
                _event(run_id, "node_status", node, "success", f"{node} 已完成"),
                writer,
                trace_events,
        )

        finished_at = _utc_now()
        update_scenario_latest_result(scenario.scenario_id, verdict)
        run = _update_run(
            run,
            status=verdict,
            finished_at=finished_at,
            duration_ms=_duration_ms(started_at, finished_at),
            verdict=verdict,
            report_id=run_id,
        )
        report = generate_report(
            run_summary=run,
            verification_results=[],
            trace_events=trace_events,
            failure_classification=None,
            output_dir=run_dir,
        )
        run["report_links"] = {
            "json": f"/api/runs/{run_id}/report?format=json",
            "html": f"/api/runs/{run_id}/report?format=html",
        }
        run["report_id"] = report["report_id"]
        save_run_payload(run)
        await _publish(
            _event(
                run_id,
                "report",
                "Reporter",
                "success",
                "报告已生成",
                payload={"report_id": run_id, "report_links": run["report_links"]},
            ),
            writer,
            trace_events,
        )
    except asyncio.CancelledError:
        finished_at = _utc_now()
        run = _update_run(
            run,
            status="cancelled",
            finished_at=finished_at,
            duration_ms=_duration_ms(started_at, finished_at),
            verdict=None,
            failure_primary="cancelled",
            report_id=run_id,
        )
        await _publish(
            _event(
                run_id,
                "error",
                "BrowserUseRun",
                "cancelled",
                "执行已取消",
            ),
            writer,
            trace_events,
        )
        generate_report(
            run_summary=run,
            verification_results=[],
            trace_events=trace_events,
            failure_classification=None,
            output_dir=run_dir,
        )
        save_run_payload(run)
    except FixturePreconditionError as exc:
        finished_at = _utc_now()
        run = _update_run(
            run,
            status="error",
            finished_at=finished_at,
            duration_ms=_duration_ms(started_at, finished_at),
            verdict=None,
            failure_primary="precondition_setup_failure",
            report_id=run_id,
        )
        await _publish(
            _event(
                run_id,
                "error",
                "FixtureResolver",
                "failed",
                f"前置条件未满足: {exc}",
            ),
            writer,
            trace_events,
        )
        generate_report(
            run_summary=run,
            verification_results=[],
            trace_events=trace_events,
            failure_classification=None,
            output_dir=run_dir,
        )
        save_run_payload(run)
    except Exception as exc:
        finished_at = _utc_now()
        run = _update_run(
            run,
            status="error",
            finished_at=finished_at,
            duration_ms=_duration_ms(started_at, finished_at),
            verdict="fail",
            failure_primary="execution_error",
            report_id=run_id,
        )
        await _publish(
            _event(
                run_id,
                "error",
                "BrowserUseRun",
                "failed",
                f"{exc.__class__.__name__}: {exc}",
            ),
            writer,
            trace_events,
        )
        generate_report(
            run_summary=run,
            verification_results=[],
            trace_events=trace_events,
            failure_classification=None,
            output_dir=run_dir,
        )
        save_run_payload(run)
    finally:
        _ACTIVE_RUN_IDS.discard(run_id)


def run_can_start(scenario_ids: list[str]) -> bool:
    return all(get_scenario_payload(scenario_id) is not None for scenario_id in scenario_ids)


class _BrowserUseLogCapture(logging.Handler):
    _LOGGER_NAMES = ("browser_use", "bubus")

    def __init__(
        self,
        *,
        run_id: str,
        run_dir: Path,
        writer: TraceWriter,
        trace_events: list[TraceEvent],
        settings: Settings,
    ) -> None:
        super().__init__(level=logging.INFO)
        self.run_id = run_id
        self.run_dir = run_dir
        self.writer = writer
        self.trace_events = trace_events
        self.loop = asyncio.get_running_loop()
        self.log_path = run_dir / "browser-use.log"
        self.secret_values = _secret_values(settings)
        self._previous_levels: dict[str, int] = {}

    def __enter__(self) -> _BrowserUseLogCapture:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.touch(exist_ok=True)
        for logger_name in self._LOGGER_NAMES:
            logger = logging.getLogger(logger_name)
            self._previous_levels[logger_name] = logger.level
            if logger.level == logging.NOTSET or logger.level > logging.INFO:
                logger.setLevel(logging.INFO)
            logger.addHandler(self)
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        for logger_name in self._LOGGER_NAMES:
            logger = logging.getLogger(logger_name)
            logger.removeHandler(self)
            logger.setLevel(self._previous_levels[logger_name])

    def emit(self, record: logging.LogRecord) -> None:
        message = self._redact(record.getMessage())
        if not message:
            return
        line = f"{_utc_now()} {record.levelname} [{record.name}] {message}"
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{line}\n")
        event = _event(
            self.run_id,
            "browser_step",
            "BrowserUseRun",
            "running",
            message,
            payload={
                "kind": "browser_use_log",
                "logger": record.name,
                "level": record.levelname,
                "text": message,
                "artifact_path": "browser-use.log",
            },
        )
        self.writer.append(event)
        self.trace_events.append(event)
        self.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(get_event_bus().publish(event))
        )

    def _redact(self, value: str) -> str:
        redacted = value
        for secret in self.secret_values:
            redacted = redacted.replace(secret, "<secret>")
        return redacted


def _secret_values(settings: Settings) -> list[str]:
    values: list[str] = []
    for field_name in (
        "openai_compatible_api_key",
        "deepseek_api_key",
        "browser_use_api_key",
        "glm_api_key",
        "fourga_password",
    ):
        value = getattr(settings, field_name, None)
        if value is None:
            continue
        secret_value = (
            value.get_secret_value()
            if hasattr(value, "get_secret_value")
            else str(value)
        )
        if secret_value:
            values.append(secret_value)
    return values


async def _run_browser_use_runner(
    runner: BrowserUseRunner,
    scenario: TestScenario,
    **kwargs: object,
) -> BrowserUseRunResult:
    if _should_use_windows_proactor_thread():
        return await asyncio.to_thread(
            _run_runner_in_windows_proactor_loop,
            runner,
            scenario,
            kwargs,
        )
    return await runner(scenario, **kwargs)


def _should_use_windows_proactor_thread() -> bool:
    if sys.platform != "win32":
        return False
    proactor_loop = getattr(asyncio, "ProactorEventLoop", None)
    if proactor_loop is None:
        return False
    return not isinstance(asyncio.get_running_loop(), proactor_loop)


def _run_runner_in_windows_proactor_loop(
    runner: BrowserUseRunner,
    scenario: TestScenario,
    kwargs: dict[str, object],
) -> BrowserUseRunResult:
    async def invoke_runner() -> BrowserUseRunResult:
        return await runner(scenario, **kwargs)

    proactor_loop = getattr(asyncio, "ProactorEventLoop", None)
    if proactor_loop is None:
        return asyncio.run(invoke_runner())
    loop = proactor_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(invoke_runner())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _first_scenario_payload(run: dict[str, object]) -> dict[str, object]:
    scenario_ids = run.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not scenario_ids:
        msg = "Run has no scenario_ids."
        raise ValueError(msg)
    scenario = get_scenario_payload(str(scenario_ids[0]))
    if scenario is None:
        msg = f"Scenario not found: {scenario_ids[0]}"
        raise ValueError(msg)
    return scenario


async def _publish_browser_use_result(
    run_id: str,
    result: BrowserUseRunResult,
    run_dir: Path,
    writer: TraceWriter,
    trace_events: list[TraceEvent],
) -> None:
    for index, action_name in enumerate(result.action_names, start=1):
        await _publish(
            _event(
                run_id,
                "browser_step",
                "BrowserUseRun",
                "running",
                f"browser-use action {index}: {action_name}",
                payload={"step": index, "action": action_name},
            ),
            writer,
            trace_events,
        )
    for index, screenshot_path in enumerate(result.screenshot_paths, start=1):
        persisted_path = _persist_screenshot(run_dir, screenshot_path, index)
        await _publish(
            _event(
                run_id,
                "browser_frame",
                "BrowserUseRun",
                "running",
                f"browser frame {index}",
                payload={
                    "frame_index": index,
                    "screenshot_path": persisted_path,
                },
            ),
            writer,
            trace_events,
        )


def _persist_screenshot(
    run_dir: Path,
    screenshot_path: str | None,
    index: int,
) -> str | None:
    if not screenshot_path:
        return None
    source = Path(screenshot_path)
    if not source.is_absolute() and not source.is_file():
        return source.as_posix()
    if not source.is_absolute():
        source = source.resolve()
    resolved_run_dir = run_dir.resolve()
    try:
        return source.relative_to(resolved_run_dir).as_posix()
    except ValueError:
        pass
    if not source.is_file():
        return None
    screenshots_dir = run_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".png"
    destination = screenshots_dir / f"step-{index}{suffix}"
    shutil.copy2(source, destination)
    return destination.relative_to(run_dir).as_posix()


async def _publish(
    event: TraceEvent,
    writer: TraceWriter,
    trace_events: list[TraceEvent],
) -> None:
    writer.append(event)
    trace_events.append(event)
    await get_event_bus().publish(event)


def _event(
    run_id: str,
    event_type: TraceEventType,
    node: str,
    status: str,
    message: str,
    *,
    payload: dict[str, object] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=new_event_id(),
        run_id=run_id,
        ts=_utc_now(),
        type=event_type,
        node=node,
        status=status,
        message=message,
        payload=payload or {},
    )


def _update_run(run: dict[str, object], **updates: Any) -> dict[str, object]:
    updated = dict(run)
    updated.update(updates)
    return updated


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at)
    finish = datetime.fromisoformat(finished_at)
    return round((finish - start).total_seconds() * 1000)
