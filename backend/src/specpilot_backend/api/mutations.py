from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mutations", tags=["mutations"])

MutationType = Literal["data", "flow", "expectation_inversion"]


class MutationGenerateRequest(BaseModel):
    scenario_ids: list[str]
    mutation_types: list[MutationType] = Field(
        default_factory=lambda: ["data", "flow", "expectation_inversion"]
    )
    max_per_scenario: int = Field(default=3, ge=1)


@router.post("/generate")
def generate_mutations(_: MutationGenerateRequest) -> dict[str, list[object]]:
    return {"mutations": []}
