from pathlib import Path
from typing import TypedDict

from fastapi import HTTPException

from specpilot_backend.config import Settings, get_settings

ARTIFACT_SUBDIRS = ("screenshots", "dom", "verification")


class ArtifactList(TypedDict):
    run_id: str
    files: list[str]


def ensure_run_artifact_dir(
    run_id: str, *, settings: Settings | None = None
) -> Path:
    resolved_settings = settings or get_settings()
    run_dir = (resolved_settings.artifact_root / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ARTIFACT_SUBDIRS:
        (run_dir / subdir).mkdir(exist_ok=True)
    return run_dir


def resolve_artifact_file(
    run_id: str, artifact_path: str, *, settings: Settings | None = None
) -> Path:
    resolved_settings = settings or get_settings()
    root = (resolved_settings.artifact_root / run_id).resolve()
    requested = (root / artifact_path).resolve()
    if root != requested and root not in requested.parents:
        raise HTTPException(status_code=403, detail="Artifact path traversal rejected")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return requested


def list_run_artifacts(
    run_id: str, *, settings: Settings | None = None
) -> ArtifactList:
    resolved_settings = settings or get_settings()
    run_dir = (resolved_settings.artifact_root / run_id).resolve()
    if not run_dir.exists():
        return {"run_id": run_id, "files": []}
    files = [
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    ]
    return {"run_id": run_id, "files": sorted(files)}
