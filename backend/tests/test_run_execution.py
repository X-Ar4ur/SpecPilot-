import logging
import asyncio
import threading
from pathlib import Path
from uuid import uuid4

import pytest

from specpilot_backend.agent.browser_use_runner import BrowserUseRunResult
from specpilot_backend.config import Settings
from specpilot_backend.demo import DEMO_SCENARIOS
from specpilot_backend.services import persistence
from specpilot_backend.services import run_executor
from specpilot_backend.services.run_executor import execute_run


@pytest.mark.anyio
async def test_execute_run_updates_status_and_writes_trace_and_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-run-executor-tests" / uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        deepseek_api_key="deepseek-key",
        glm_api_key="glm-key",
    )
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    scenario = DEMO_SCENARIOS[0]
    persistence.save_scenario_payload(scenario)
    run_dir = settings.artifact_root / "run_executor_001"
    run = {
        "run_id": "run_executor_001",
        "scenario_ids": [scenario["scenario_id"]],
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "verdict": None,
        "failure_primary": None,
        "failure_secondary": [],
        "artifact_dir": str(run_dir),
        "report_id": None,
    }
    persistence.save_run_payload(run)
    browser_use_screenshot = tmp_path / "browser-use-tmp" / "step_1.png"
    browser_use_screenshot.parent.mkdir(parents=True)
    browser_use_screenshot.write_bytes(b"fake-png")

    async def fake_runner(*_: object, **__: object) -> BrowserUseRunResult:
        return BrowserUseRunResult(
            success=True,
            final_result="done",
            urls=["https://demo.4gaboards.com/"],
            action_names=["navigate", "done"],
            screenshot_paths=[str(browser_use_screenshot)],
            steps=2,
        )

    await execute_run(
        "run_executor_001",
        settings=settings,
        runner=fake_runner,
    )

    updated = persistence.get_run_payload("run_executor_001")
    assert updated is not None
    assert updated["status"] == "pass"
    assert updated["verdict"] == "pass"
    assert updated["report_id"] == "run_executor_001"
    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "report.html").exists()
    trace_text = (run_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert "ScenarioLoader" in trace_text
    assert "BrowserUseRun" in trace_text
    assert "browser_step" in trace_text
    assert "screenshots/step-1.png" in trace_text
    assert str(browser_use_screenshot) not in trace_text
    assert (run_dir / "screenshots" / "step-1.png").read_bytes() == b"fake-png"
    assert (run_dir / "browser-use.log").exists()


@pytest.mark.anyio
async def test_execute_run_overwrites_scenario_latest_result_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-run-result-tests" / uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        deepseek_api_key="deepseek-key",
        glm_api_key="glm-key",
    )
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    scenario = DEMO_SCENARIOS[0]
    persistence.save_scenario_payload(scenario)

    async def failing_runner(*_: object, **__: object) -> BrowserUseRunResult:
        return BrowserUseRunResult(success=False, final_result="not done")

    async def passing_runner(*_: object, **__: object) -> BrowserUseRunResult:
        return BrowserUseRunResult(success=True, final_result="done")

    for run_id, runner in (
        ("run_result_fail_001", failing_runner),
        ("run_result_pass_001", passing_runner),
    ):
        persistence.save_run_payload(
            {
                "run_id": run_id,
                "scenario_ids": [scenario["scenario_id"]],
                "status": "queued",
                "started_at": None,
                "finished_at": None,
                "duration_ms": None,
                "verdict": None,
                "failure_primary": None,
                "failure_secondary": [],
                "artifact_dir": str(settings.artifact_root / run_id),
                "report_id": None,
            }
        )
        await execute_run(run_id, settings=settings, runner=runner)
        latest_result = persistence.list_scenario_records()[0].latest_result
        expected_result = "fail" if run_id == "run_result_fail_001" else "pass"
        assert latest_result == expected_result

    records = persistence.list_scenario_records()
    assert len(records) == 1
    assert records[0].latest_result == "pass"


@pytest.mark.anyio
async def test_execute_run_streams_and_persists_browser_use_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-run-log-tests" / uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        deepseek_api_key="deepseek-key",
        glm_api_key="glm-key",
    )
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    scenario = DEMO_SCENARIOS[0]
    persistence.save_scenario_payload(scenario)
    run_dir = settings.artifact_root / "run_log_001"
    run = {
        "run_id": "run_log_001",
        "scenario_ids": [scenario["scenario_id"]],
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "verdict": None,
        "failure_primary": None,
        "failure_secondary": [],
        "artifact_dir": str(run_dir),
        "report_id": None,
    }
    persistence.save_run_payload(run)

    async def fake_runner(*_: object, **__: object) -> BrowserUseRunResult:
        logging.getLogger("browser_use.Agent").info(
            "Step 1: clicked %s",
            "SpecPilot Acceptance Board",
        )
        return BrowserUseRunResult(success=True, final_result="done")

    await execute_run("run_log_001", settings=settings, runner=fake_runner)

    trace_text = (run_dir / "trace.jsonl").read_text(encoding="utf-8")
    log_text = (run_dir / "browser-use.log").read_text(encoding="utf-8")
    assert "browser_use_log" in trace_text
    assert "Step 1: clicked SpecPilot Acceptance Board" in trace_text
    assert "Step 1: clicked SpecPilot Acceptance Board" in log_text


@pytest.mark.anyio
async def test_execute_run_marks_run_cancelled_when_runner_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-run-cancel-tests" / uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        deepseek_api_key="deepseek-key",
        glm_api_key="glm-key",
    )
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    scenario = DEMO_SCENARIOS[0]
    persistence.save_scenario_payload(scenario)
    run_dir = settings.artifact_root / "run_cancelled_001"
    run = {
        "run_id": "run_cancelled_001",
        "scenario_ids": [scenario["scenario_id"]],
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "verdict": None,
        "failure_primary": None,
        "failure_secondary": [],
        "artifact_dir": str(run_dir),
        "report_id": None,
    }
    persistence.save_run_payload(run)

    async def cancelled_runner(*_: object, **__: object) -> BrowserUseRunResult:
        raise asyncio.CancelledError

    await execute_run(
        "run_cancelled_001",
        settings=settings,
        runner=cancelled_runner,
    )

    updated = persistence.get_run_payload("run_cancelled_001")
    assert updated is not None
    assert updated["status"] == "cancelled"
    assert updated["verdict"] is None
    assert updated["failure_primary"] == "cancelled"
    assert updated["finished_at"] is not None
    assert updated["duration_ms"] is not None
    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "report.json").exists()
    trace_text = (run_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert "执行已取消" in trace_text


@pytest.mark.anyio
async def test_execute_run_uses_threaded_runner_when_windows_loop_lacks_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-run-thread-tests" / uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        deepseek_api_key="deepseek-key",
        glm_api_key="glm-key",
    )
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    scenario = DEMO_SCENARIOS[0]
    persistence.save_scenario_payload(scenario)
    run = {
        "run_id": "run_threaded_001",
        "scenario_ids": [scenario["scenario_id"]],
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "verdict": None,
        "failure_primary": None,
        "failure_secondary": [],
        "artifact_dir": str(settings.artifact_root / "run_threaded_001"),
        "report_id": None,
    }
    persistence.save_run_payload(run)
    main_thread_id = threading.get_ident()
    runner_thread_ids: list[int] = []
    monkeypatch.setattr(
        run_executor,
        "_should_use_windows_proactor_thread",
        lambda: True,
    )

    async def fake_runner(*_: object, **__: object) -> BrowserUseRunResult:
        runner_thread_ids.append(threading.get_ident())
        return BrowserUseRunResult(success=True, final_result="done")

    await execute_run(
        "run_threaded_001",
        settings=settings,
        runner=fake_runner,
    )

    assert runner_thread_ids
    assert runner_thread_ids[0] != main_thread_id
