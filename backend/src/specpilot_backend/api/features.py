from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from specpilot_backend.config import get_settings
from specpilot_backend.services import manual_pipeline
from specpilot_backend.services.persistence import list_feature_payloads
from specpilot_backend.services.persistence import create_job_record, save_feature_payload, update_job_record

router = APIRouter(prefix="/api/features", tags=["features"])


class FeatureExtractRequest(BaseModel):
    index_id: str
    min_evidence: int = Field(default=1, ge=1)


@router.post("/extract")
def extract_features(
    payload: FeatureExtractRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    job = create_job_record(
        job_type="feature_extract",
        stage="queued",
        message="等待提取功能点",
    )
    background_tasks.add_task(_run_feature_job, job.job_id, payload.index_id)
    return {"job_id": job.job_id, "status": "queued"}


@router.get("")
def list_features() -> dict[str, list[dict[str, object]]]:
    return {"items": list_feature_payloads()}


def _run_feature_job(job_id: str, index_id: str) -> None:
    try:
        update_job_record(job_id, status="running", stage="features", progress=20)
        chunks = manual_pipeline.load_chunks_manifest(index_id, manifest_type="indexes")
        features = manual_pipeline.extract_features_from_chunks(chunks, get_settings())
        for feature in features:
            save_feature_payload(feature)
        update_job_record(
            job_id,
            status="succeeded",
            stage="done",
            progress=100,
            message="功能点提取完成",
            result={"features_count": len(features), "index_id": index_id},
        )
    except Exception as exc:
        update_job_record(job_id, status="failed", error=str(exc))
