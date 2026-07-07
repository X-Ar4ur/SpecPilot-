from typing import Literal

from pydantic import BaseModel, ConfigDict

RunStatus = Literal[
    "queued",
    "running",
    "pass",
    "fail",
    "needs_review",
    "cancelled",
    "error",
]
RunVerdict = Literal["pass", "fail", "needs_review"]


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    scenario_ids: list[str]
    status: RunStatus
    started_at: str | None
    finished_at: str | None
    duration_ms: int | None
    verdict: RunVerdict | None
    failure_primary: str | None
    failure_secondary: list[str]
    artifact_dir: str
    report_id: str | None
