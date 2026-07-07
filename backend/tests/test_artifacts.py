from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from specpilot_backend.config import Settings
from specpilot_backend.services.artifacts import (
    ensure_run_artifact_dir,
    list_run_artifacts,
    resolve_artifact_file,
)


@pytest.fixture
def settings() -> Settings:
    tmp_path = Path(".pytest_cache") / "specpilot-tests" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    return Settings(_env_file=None, artifact_root=tmp_path / "runs")


def test_ensure_run_artifact_dir_creates_expected_tree(settings: Settings) -> None:
    run_dir = ensure_run_artifact_dir("run_001", settings=settings)

    assert run_dir == (settings.artifact_root / "run_001").resolve()
    assert (run_dir / "screenshots").is_dir()
    assert (run_dir / "dom").is_dir()
    assert (run_dir / "verification").is_dir()


def test_resolve_artifact_file_stays_under_run_directory(settings: Settings) -> None:
    run_dir = ensure_run_artifact_dir("run_001", settings=settings)
    report = run_dir / "report.json"
    report.write_text("{}", encoding="utf-8")

    resolved = resolve_artifact_file("run_001", "report.json", settings=settings)

    assert resolved == report.resolve()


@pytest.mark.parametrize("unsafe_path", ["../secret.txt", "screenshots/../../secret"])
def test_resolve_artifact_file_rejects_path_traversal(
    settings: Settings, unsafe_path: str
) -> None:
    ensure_run_artifact_dir("run_001", settings=settings)

    with pytest.raises(HTTPException) as exc_info:
        resolve_artifact_file("run_001", unsafe_path, settings=settings)

    assert exc_info.value.status_code == 403


def test_resolve_artifact_file_rejects_missing_file(settings: Settings) -> None:
    ensure_run_artifact_dir("run_001", settings=settings)

    with pytest.raises(HTTPException) as exc_info:
        resolve_artifact_file("run_001", "missing.json", settings=settings)

    assert exc_info.value.status_code == 404


def test_list_run_artifacts_returns_relative_files(settings: Settings) -> None:
    run_dir = ensure_run_artifact_dir("run_001", settings=settings)
    (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
    (run_dir / "screenshots" / "step-1.png").write_text("image", encoding="utf-8")

    listing = list_run_artifacts("run_001", settings=settings)

    assert listing["run_id"] == "run_001"
    assert "trace.jsonl" in listing["files"]
    assert "screenshots/step-1.png" in listing["files"]
