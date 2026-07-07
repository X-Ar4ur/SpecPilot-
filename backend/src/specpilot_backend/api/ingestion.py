from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from specpilot_backend.ids import new_id
from specpilot_backend.services import manual_pipeline
from specpilot_backend.services.persistence import create_job_record, update_job_record

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


class CrawlRequest(BaseModel):
    base_url: str = "https://docs.4gaboards.com/"
    sections: list[str] = Field(default_factory=lambda: ["user-manual", "admin-manual"])
    language: str = "en"


class IndexRequest(BaseModel):
    crawl_id: str
    force: bool = False


@router.post("/crawl")
def crawl_manual(payload: CrawlRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    job = create_job_record(
        job_type="manual_crawl",
        stage="queued",
        message="等待抓取手册",
    )
    crawl_id = new_id("crawl")
    request = manual_pipeline.ManualPipelineRequest(
        base_url=payload.base_url,
        sections=tuple(payload.sections),
        language=payload.language,
    )
    background_tasks.add_task(_run_crawl_job, job.job_id, crawl_id, request)
    return {"crawl_id": crawl_id, "job_id": job.job_id, "status": "queued"}


@router.post("/index")
def index_manual(payload: IndexRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    job = create_job_record(
        job_type="manual_index",
        stage="queued",
        message="等待索引手册证据",
    )
    index_id = new_id("idx")
    background_tasks.add_task(_run_index_job, job.job_id, index_id, payload.crawl_id)
    return {"index_id": index_id, "job_id": job.job_id, "status": "queued"}


def _run_crawl_job(
    job_id: str,
    expected_crawl_id: str,
    request: manual_pipeline.ManualPipelineRequest,
) -> None:
    try:
        update_job_record(job_id, status="running", stage="crawl", progress=10)
        output = manual_pipeline.crawl_manual_chunks(request)
        result = {
            "crawl_id": output.crawl_id,
            "requested_crawl_id": expected_crawl_id,
            "pages_count": len(output.pages),
            "chunks_count": len(output.chunks),
        }
        update_job_record(
            job_id,
            status="succeeded",
            stage="done",
            progress=100,
            message="手册抓取完成",
            result=result,
        )
    except Exception as exc:
        update_job_record(job_id, status="failed", error=str(exc))


def _run_index_job(job_id: str, index_id: str, crawl_id: str) -> None:
    try:
        update_job_record(job_id, status="running", stage="index", progress=10)
        chunks = manual_pipeline.load_chunks_manifest(crawl_id, manifest_type="crawls")
        actual_index_id = manual_pipeline.index_manual_chunks(chunks, crawl_id)
        update_job_record(
            job_id,
            status="succeeded",
            stage="done",
            progress=100,
            message="手册索引完成",
            result={
                "index_id": actual_index_id,
                "requested_index_id": index_id,
                "chunks_count": len(chunks),
            },
        )
    except Exception as exc:
        update_job_record(job_id, status="failed", error=str(exc))
