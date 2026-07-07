from pathlib import Path
from uuid import uuid4

from specpilot_backend.config import Settings
from specpilot_backend.services import persistence


def _run_payload(run_id: str, status: str, artifact_root: Path) -> dict[str, object]:
    return {
        "run_id": run_id,
        "scenario_ids": ["sc_demo_create_card"],
        "status": status,
        "started_at": "2026-05-07T07:39:00+00:00" if status == "running" else None,
        "finished_at": None,
        "duration_ms": None,
        "verdict": None,
        "failure_primary": None,
        "failure_secondary": [],
        "artifact_dir": str(artifact_root / run_id),
        "report_id": None,
    }


def test_mark_orphaned_running_runs_cancelled_leaves_active_runs_running() -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-run-reconcile-tests" / uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    persistence.save_run_payload(
        _run_payload("run_orphaned", "running", settings.artifact_root)
    )
    persistence.save_run_payload(
        _run_payload("run_active", "running", settings.artifact_root)
    )
    persistence.save_run_payload(
        _run_payload("run_queued", "queued", settings.artifact_root)
    )

    changed = persistence.mark_orphaned_running_runs_cancelled({"run_active"})

    orphaned = persistence.get_run_payload("run_orphaned")
    active = persistence.get_run_payload("run_active")
    queued = persistence.get_run_payload("run_queued")
    assert changed == 1
    assert orphaned is not None
    assert orphaned["status"] == "cancelled"
    assert orphaned["failure_primary"] == "interrupted"
    assert orphaned["finished_at"] is not None
    assert orphaned["duration_ms"] is None
    assert active is not None
    assert active["status"] == "running"
    assert queued is not None
    assert queued["status"] == "queued"
