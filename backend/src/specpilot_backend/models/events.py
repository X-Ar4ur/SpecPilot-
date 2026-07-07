from typing import Literal

from pydantic import BaseModel, ConfigDict

TraceEventType = Literal[
    "node_status",
    "browser_step",
    "browser_frame",
    "verification",
    "classification",
    "repair",
    "report",
    "error",
]


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    run_id: str
    ts: str
    type: TraceEventType
    node: str | None
    status: str | None
    message: str | None
    payload: dict[str, object]
