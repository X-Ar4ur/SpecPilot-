from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Priority = Literal["P0", "P1", "P2"]
Difficulty = Literal["simple", "medium", "hard"]
ExpectationType = Literal[
    "element_visible",
    "text_present",
    "url_match",
    "element_state",
    "containment",
    "semantic",
]
ReviewStatus = Literal["auto_validated", "needs_review", "rejected"]
DataDependency = Literal["none", "self_seeding", "interactive"]
FixtureKind = Literal["project", "board", "list", "card"]

# Attributes a fixture token may reference per kind. Bindings resolve exactly
# these from the 4ga inventory, so generation must not reference others.
FIXTURE_ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "card": ("title", "list_name", "board_name", "project_name"),
    "list": ("name", "board_name", "project_name"),
    "board": ("name", "project_name"),
    "project": ("name",),
}

FORBIDDEN_SCENARIO_FIELDS = {
    "locator",
    "selector",
    "xpath",
    "element_id",
    "element_index",
    "css",
    "css_selector",
}


def find_forbidden_field(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if str(key) in FORBIDDEN_SCENARIO_FIELDS:
                return str(key)
            found = find_forbidden_field(nested_value)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_forbidden_field(item)
            if found is not None:
                return found
    return None


class TestStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1)
    action: str = Field(min_length=1)


class Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ExpectationType
    description: str = Field(min_length=1)
    params: dict[str, object]


class FixtureSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1)
    kind: FixtureKind
    parent_ref: str | None = None
    required_attrs: list[str] = Field(default_factory=lambda: ["title"])
    allow_create: bool = True


class TestScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    feature_id: str
    title: str
    priority: Priority
    difficulty: Difficulty
    source_urls: list[str] = Field(min_length=1)
    evidence_quotes: list[str] = Field(min_length=1)
    preconditions: list[str]
    test_data: dict[str, object]
    steps: list[TestStep] = Field(min_length=1)
    expectations: list[Expectation]
    max_steps: int = Field(ge=1)
    requires_visual_check: bool
    review_status: ReviewStatus
    is_mutation: bool = False
    data_dependency: DataDependency = "none"
    fixtures: list[FixtureSlot] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_locator_fields(cls, data: Any) -> Any:
        found = find_forbidden_field(data)
        if found is not None:
            msg = f"Scenario contains forbidden zero-locator field: {found}"
            raise ValueError(msg)
        return data
