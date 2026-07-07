from typing import Literal

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from specpilot_backend.config import get_settings
from specpilot_backend.services.manual_pipeline import (
    ManualPipelineRequest,
    run_manual_pipeline,
)
from specpilot_backend.services.persistence import create_job_record

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class ManualPipelineApiRequest(BaseModel):
    base_url: str = "https://docs.4gaboards.com/"
    sections: list[str] = Field(default_factory=lambda: ["user-manual", "admin-manual"])
    language: str = "en"
    max_pages: int = Field(default=250, ge=1, le=1000)
    max_scenarios_per_feature: int = Field(default=3, ge=1, le=10)
    start_stage: Literal["crawl", "index", "features", "scenarios"] = "crawl"
    resume_from_job_id: str | None = None
    crawl_id: str | None = None
    index_id: str | None = None
    feature_ids: list[str] = Field(default_factory=list)


@router.post("/manual-to-scenarios")
def start_manual_pipeline(
    payload: ManualPipelineApiRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    job = create_job_record(
        job_type="manual_pipeline",
        stage="queued",
        message="等待执行真实手册生成",
    )
    request = ManualPipelineRequest(
        base_url=payload.base_url,
        sections=tuple(payload.sections),
        language=payload.language,
        max_pages=payload.max_pages,
        max_scenarios_per_feature=payload.max_scenarios_per_feature,
        start_stage=payload.start_stage,
        resume_from_job_id=payload.resume_from_job_id,
        crawl_id=payload.crawl_id,
        index_id=payload.index_id,
        feature_ids=tuple(payload.feature_ids),
    )
    background_tasks.add_task(
        run_manual_pipeline,
        job.job_id,
        request,
        settings=get_settings(),
    )
    return {"job_id": job.job_id, "status": "queued"}
