from typing import Literal

from pydantic import ConfigDict, Field

from specpilot_backend.models.scenarios import TestScenario

MutationType = Literal["data", "flow", "expectation_inversion"]
DetectionOutcome = Literal[
    "detected_correctly",
    "missed",
    "false_positive",
    "true_negative",
]


class MutatedScenario(TestScenario):
    model_config = ConfigDict(extra="forbid")

    is_mutation: bool = True
    mutation_id: str
    source_scenario_id: str
    mutation_type: MutationType
    mutation_description: str = Field(min_length=1)
    mutation_params: dict[str, object]
    expected_detection: bool
    detection_outcome: DetectionOutcome | None = None
