import asyncio
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from specpilot_backend.config import get_settings
from specpilot_backend.fixtures.binding_service import (
    FixtureNotConfiguredError,
    collect_unready_bindings,
)
from specpilot_backend.ids import new_id
from specpilot_backend.events.sse import iter_sse_events
from specpilot_backend.services.artifacts import (
    ArtifactList,
    ensure_run_artifact_dir,
    list_run_artifacts,
    resolve_artifact_file,
)
from specpilot_backend.services.persistence import (
    get_run_payload,
    list_run_payloads,
    mark_orphaned_running_runs_cancelled,
    save_run_payload,
)
from specpilot_backend.services.run_executor import (
    active_run_ids,
    execute_run,
    run_can_start,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    scenario_ids: list[str] = Field(min_length=1)
    mode: str = "single"
    config: dict[str, object] = Field(default_factory=dict)


@router.post("")
async def create_run(request: CreateRunRequest) -> dict[str, str]:
    try:
        unready = await collect_unready_bindings(request.scenario_ids)
    except FixtureNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if unready:
        raise HTTPException(
            status_code=409,
            detail={"reason": "fixtures_unbound", "scenarios": unready},
        )
    run_id = new_id("run")
    artifact_dir = ensure_run_artifact_dir(run_id, settings=get_settings())
    run = {
        "run_id": run_id,
        "scenario_ids": request.scenario_ids,
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "verdict": None,
        "failure_primary": None,
        "failure_secondary": [],
        "artifact_dir": str(artifact_dir),
        "report_id": None,
    }
    save_run_payload(run)
    if run_can_start(request.scenario_ids):
        asyncio.create_task(execute_run(run_id))
    return {"run_id": run_id, "status": "queued", "live_url": f"/runs/live/{run_id}"}


@router.get("")
def list_runs() -> dict[str, list[dict[str, object]]]:
    mark_orphaned_running_runs_cancelled(active_run_ids())
    return {"items": list_run_payloads()}


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = get_run_payload(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/events")
def stream_run_events(run_id: str, request: Request) -> StreamingResponse:
    run = get_run_payload(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    replay_only = "text/event-stream" not in request.headers.get("accept", "")
    trace_path = Path(str(run["artifact_dir"])) / "trace.jsonl"
    return StreamingResponse(
        iter_sse_events(run_id, replay_only=replay_only, trace_path=trace_path),
        media_type="text/event-stream",
    )


@router.get("/{run_id}/trace")
def get_run_trace(run_id: str) -> dict[str, list[dict[str, object]]]:
    run = get_run_payload(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    trace_path = Path(str(run["artifact_dir"])) / "trace.jsonl"
    if not trace_path.exists():
        return {"items": []}
    items = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(__import__("json").loads(line))
    return {"items": items}


@router.get("/{run_id}/artifacts")
def get_run_artifacts(run_id: str) -> ArtifactList:
    if get_run_payload(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return list_run_artifacts(run_id, settings=get_settings())


@router.get("/{run_id}/artifacts/{artifact_path:path}")
def get_run_artifact_file(run_id: str, artifact_path: str) -> FileResponse:
    if get_run_payload(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    resolved = resolve_artifact_file(run_id, artifact_path, settings=get_settings())
    return FileResponse(resolved)


@router.get("/{run_id}/report")
def get_run_report_file(
    run_id: str,
    format: Literal["json", "html", "pdf"] = Query(default="html"),
) -> FileResponse:
    if get_run_payload(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    filename = f"report.{format}"
    resolved = resolve_artifact_file(run_id, filename, settings=get_settings())
    media_types = {
        "json": "application/json",
        "html": "text/html; charset=utf-8",
        "pdf": "application/pdf",
    }
    return FileResponse(
        resolved,
        media_type=media_types[format],
        filename=filename,
    )
