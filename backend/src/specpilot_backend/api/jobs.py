from fastapi import APIRouter, HTTPException

from specpilot_backend.services.persistence import get_job_payload

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = get_job_payload(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
