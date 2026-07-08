import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from specpilot_backend.config import get_settings
from specpilot_backend.fixtures.binding_service import (
    FixtureNotConfiguredError,
    ScenarioNotFoundError,
    get_binding_status,
)
from specpilot_backend.fixtures.fourga_client import FourgaApiError
from specpilot_backend.fixtures.models import ScenarioBindingStatus
from specpilot_backend.ingestion.chunker import ManualChunk
from specpilot_backend.reports.scenario_status import render_scenario_status_report
from specpilot_backend.services import manual_pipeline
from specpilot_backend.services.persistence import (
    create_job_record,
    get_scenario_payload,
    list_feature_payloads,
    list_scenario_records,
    save_scenario_payload,
    update_job_record,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class ScenarioGenerateRequest(BaseModel):
    feature_ids: list[str]
    max_scenarios_per_feature: int = Field(default=3, ge=1)


@router.post("/generate")
def generate_scenarios(
    payload: ScenarioGenerateRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    job = create_job_record(
        job_type="scenario_generate",
        stage="queued",
        message="等待生成测试场景",
    )
    background_tasks.add_task(
        _run_scenario_job,
        job.job_id,
        payload.feature_ids,
        payload.max_scenarios_per_feature,
    )
    return {"job_id": job.job_id, "status": "queued"}


@router.get("")
def list_scenarios(
    feature_id: str | None = None,
    priority: str | None = None,
    difficulty: str | None = None,
    review_status: str | None = None,
    latest_result: str | None = None,
    is_mutation: bool | None = Query(default=None),
) -> dict[str, list[dict[str, object]]]:
    records = list_scenario_records(
        feature_id=feature_id,
        priority=priority,
        difficulty=difficulty,
        review_status=review_status,
        latest_result=latest_result,
        is_mutation=is_mutation,
    )
    return {
        "items": [
            {
                "scenario_id": record.scenario_id,
                "feature_id": record.feature_id,
                "title": _scenario_title(record.scenario_id),
                "priority": record.priority,
                "difficulty": record.difficulty,
                "review_status": record.review_status,
                "latest_result": record.latest_result,
                "is_mutation": record.is_mutation,
            }
            for record in records
        ]
    }


@router.get("/status-report.html")
def export_scenario_status_report() -> HTMLResponse:
    records = list_scenario_records()
    return HTMLResponse(render_scenario_status_report(records))


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str) -> dict[str, object]:
    scenario = get_scenario_payload(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.get("/{scenario_id}/binding")
async def get_scenario_binding(scenario_id: str) -> ScenarioBindingStatus:
    try:
        return await get_binding_status(scenario_id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scenario not found") from exc
    except FixtureNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FourgaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="could not reach the 4ga target instance",
        ) from exc


def _scenario_title(scenario_id: str) -> object:
    scenario = get_scenario_payload(scenario_id)
    if scenario is None:
        return scenario_id
    return scenario["title"]


def _run_scenario_job(
    job_id: str,
    feature_ids: list[str],
    max_scenarios_per_feature: int,
) -> None:
    try:
        update_job_record(job_id, status="running", stage="scenarios", progress=20)
        features = [
            feature
            for feature in list_feature_payloads()
            if str(feature["feature_id"]) in feature_ids
        ]
        chunks = [
            ManualChunk(
                content=str(quote),
                metadata={
                    "source_url": str(url),
                    "module": feature.get("module", "Other"),
                    "is_ui_operational": True,
                },
            )
            for feature in features
            for quote in _string_list(feature.get("evidence_quotes"))
            for url in _string_list(feature.get("source_urls"))
        ]
        scenarios = manual_pipeline.generate_scenarios_from_features(
            features,
            chunks,
            get_settings(),
            max_scenarios_per_feature=max_scenarios_per_feature,
        )
        for scenario in scenarios:
            save_scenario_payload(scenario)
        update_job_record(
            job_id,
            status="succeeded",
            stage="done",
            progress=100,
            message="测试场景生成完成",
            result={"scenarios_count": len(scenarios)},
        )
    except Exception as exc:
        update_job_record(job_id, status="failed", error=str(exc))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
