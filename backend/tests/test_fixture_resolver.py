from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from specpilot_backend.agent.browser_use_runner import BrowserUseRunResult
from specpilot_backend.config import Settings
from specpilot_backend.fixtures.binding_service import (
    FixturePreconditionError,
    collect_unready_bindings,
    resolve_scenario_fixtures,
)
from specpilot_backend.main import app
from specpilot_backend.services import persistence
from specpilot_backend.services.run_executor import execute_run

TARGET = "http://localhost:1337"


@pytest.fixture
def paths(tmp_path: Path) -> Path:
    persistence.configure_database(f"sqlite:///{tmp_path / 'specpilot.db'}")
    persistence.create_tables()
    return tmp_path


def _settings(paths: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{paths / 'specpilot.db'}",
        artifact_root=paths / "runs",
        fourga_username="demo",
        fourga_password="demo",
        fourga_api_base_url=TARGET,
    )


def _scenario_payload(
    scenario_id: str,
    *,
    data_dependency: str,
    fixtures: list[dict[str, object]],
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "scenario_id": scenario_id,
        "feature_id": "ft1",
        "title": "t",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/x"],
        "evidence_quotes": ["q"],
        "preconditions": [],
        "test_data": {},
        "steps": [{"order": 1, "action": "a"}],
        "expectations": [],
        "max_steps": 5,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
        "data_dependency": data_dependency,
        "fixtures": fixtures,
    }
    payload.update(extra)
    return payload


def _save_binding(scenario_id: str, ref: str, entity_id: str, title: str) -> None:
    persistence.save_fixture_binding(
        {
            "scenario_id": scenario_id,
            "target_app_url": TARGET,
            "ref": ref,
            "entity_kind": "card",
            "entity_id": entity_id,
            "resolved_values": {"title": title},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )


def _save_run(run_id: str, scenario_id: str, run_dir: Path) -> None:
    persistence.save_run_payload(
        {
            "run_id": run_id,
            "scenario_ids": [scenario_id],
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
    )


# --- resolve_scenario_fixtures ---------------------------------------------


def test_resolve_passthrough_for_non_interactive(paths: Path) -> None:
    payload = _scenario_payload("s", data_dependency="none", fixtures=[])

    assert resolve_scenario_fixtures(payload, settings=_settings(paths)) is payload


def test_resolve_replaces_tokens_with_bound_values(paths: Path) -> None:
    _save_binding("s", "target_card", "1000", "完成季度报告")
    payload = _scenario_payload(
        "s",
        data_dependency="interactive",
        fixtures=[{"ref": "target_card", "kind": "card"}],
        test_data={"card_title": "{{fixture.target_card.title}}"},
        steps=[{"order": 1, "action": "打开 {{fixture.target_card.title}}"}],
        expectations=[
            {
                "type": "element_visible",
                "description": "d",
                "params": {"text": "{{fixture.target_card.title}}"},
            }
        ],
    )

    out = resolve_scenario_fixtures(payload, settings=_settings(paths))

    assert out["test_data"] == {"card_title": "完成季度报告"}
    assert out["steps"] == [{"order": 1, "action": "打开 完成季度报告"}]
    assert out["expectations"] == [
        {
            "type": "element_visible",
            "description": "d",
            "params": {"text": "完成季度报告"},
        }
    ]


def test_resolve_accepts_legacy_title_token_for_board(paths: Path) -> None:
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc_legacy_board_title",
            "target_app_url": TARGET,
            "ref": "target_board",
            "entity_kind": "board",
            "entity_id": "10",
            "resolved_values": {"name": "自动化看板", "project_name": "项目"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    payload = _scenario_payload(
        "sc_legacy_board_title",
        data_dependency="interactive",
        fixtures=[{"ref": "target_board", "kind": "board"}],
        test_data={"board_name": "{{fixture.target_board.title}}"},
        steps=[{"order": 1, "action": "打开 {{fixture.target_board.title}}"}],
    )

    out = resolve_scenario_fixtures(payload, settings=_settings(paths))

    assert out["test_data"] == {"board_name": "自动化看板"}
    assert out["steps"] == [{"order": 1, "action": "打开 自动化看板"}]


def test_resolve_missing_binding_raises(paths: Path) -> None:
    payload = _scenario_payload(
        "s2",
        data_dependency="interactive",
        fixtures=[{"ref": "target_card", "kind": "card"}],
        test_data={"x": "{{fixture.target_card.title}}"},
    )

    with pytest.raises(FixturePreconditionError) as exc_info:
        resolve_scenario_fixtures(payload, settings=_settings(paths))

    assert exc_info.value.unresolved_refs == ["target_card"]


# --- collect_unready_bindings ----------------------------------------------


@pytest.mark.anyio
async def test_collect_unready_flags_unbound_interactive(paths: Path) -> None:
    persistence.save_scenario_payload(
        _scenario_payload(
            "sc_i",
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
        )
    )

    unready = await collect_unready_bindings(["sc_i"], settings=_settings(paths))

    assert len(unready) == 1
    assert unready[0]["scenario_id"] == "sc_i"
    slots = unready[0]["slots"]
    assert isinstance(slots, list)
    assert slots[0]["ref"] == "target_card"


@pytest.mark.anyio
async def test_collect_unready_ignores_non_interactive(paths: Path) -> None:
    persistence.save_scenario_payload(
        _scenario_payload("sc_n", data_dependency="none", fixtures=[])
    )

    unready = await collect_unready_bindings(["sc_n"], settings=_settings(paths))

    assert unready == []


# --- execute_run -----------------------------------------------------------


@pytest.mark.anyio
async def test_execute_run_precondition_failure_sets_error(paths: Path) -> None:
    settings = _settings(paths)
    persistence.save_scenario_payload(
        _scenario_payload(
            "sc_pre",
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
            test_data={"card_title": "{{fixture.target_card.title}}"},
        )
    )
    _save_run("run_pre", "sc_pre", settings.artifact_root / "run_pre")
    runner_called: list[bool] = []

    async def fake_runner(*_: object, **__: object) -> BrowserUseRunResult:
        runner_called.append(True)
        return BrowserUseRunResult(success=True, final_result="x")

    await execute_run("run_pre", settings=settings, runner=fake_runner)

    run = persistence.get_run_payload("run_pre")
    assert run is not None
    assert run["status"] == "error"
    assert run["failure_primary"] == "precondition_setup_failure"
    assert run["verdict"] is None
    assert runner_called == []


@pytest.mark.anyio
async def test_execute_run_resolves_tokens_before_runner(paths: Path) -> None:
    settings = _settings(paths)
    _save_binding("sc_ok", "target_card", "1000", "完成季度报告")
    persistence.save_scenario_payload(
        _scenario_payload(
            "sc_ok",
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
            test_data={"card_title": "{{fixture.target_card.title}}"},
        )
    )
    _save_run("run_ok", "sc_ok", settings.artifact_root / "run_ok")
    captured: dict[str, object] = {}

    async def fake_runner(scenario: Any, **__: object) -> BrowserUseRunResult:
        captured["card_title"] = scenario.test_data.get("card_title")
        return BrowserUseRunResult(success=True, final_result="done")

    await execute_run("run_ok", settings=settings, runner=fake_runner)

    assert captured["card_title"] == "完成季度报告"
    run = persistence.get_run_payload("run_ok")
    assert run is not None
    assert run["status"] == "pass"


# --- run-launch gating (HTTP) ----------------------------------------------


@pytest.fixture
def client(paths: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = _settings(paths)
    monkeypatch.setattr(
        "specpilot_backend.api.settings.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "specpilot_backend.fixtures.binding_service.get_settings", lambda: settings
    )
    with TestClient(app) as test_client:
        yield test_client


def test_create_run_rejected_when_fixtures_unbound(client: TestClient) -> None:
    persistence.save_scenario_payload(
        _scenario_payload(
            "sc_gate",
            data_dependency="interactive",
            fixtures=[{"ref": "target_card", "kind": "card"}],
        )
    )

    response = client.post("/api/runs", json={"scenario_ids": ["sc_gate"]})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"] == "fixtures_unbound"
    assert detail["scenarios"][0]["scenario_id"] == "sc_gate"
