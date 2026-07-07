from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from specpilot_backend.api import (
    doctor,
    features,
    fixtures,
    ingestion,
    jobs,
    mutations,
    pipeline,
    reports,
    runs,
    scenarios,
    settings,
)
from specpilot_backend.services.persistence import (
    create_tables,
    mark_orphaned_running_runs_cancelled,
)
from specpilot_backend.services.run_executor import active_run_ids

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_tables()
    mark_orphaned_running_runs_cancelled(active_run_ids())
    yield


app = FastAPI(title="SpecPilot Backend", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ingestion.router)
app.include_router(jobs.router)
app.include_router(pipeline.router)
app.include_router(features.router)
app.include_router(fixtures.router)
app.include_router(scenarios.router)
app.include_router(runs.router)
app.include_router(mutations.router)
app.include_router(reports.router)
app.include_router(settings.router)
app.include_router(doctor.router)
