from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from specpilot_backend.models.scenarios import DataDependency, FixtureKind


class InventoryCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class InventoryList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    cards: list[InventoryCard] = Field(default_factory=list)


class InventoryBoard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    lists: list[InventoryList] = Field(default_factory=list)


class InventoryProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    boards: list[InventoryBoard] = Field(default_factory=list)


class FixtureInventory(BaseModel):
    """Project -> Board -> List -> Card tree of the target 4ga instance.

    Backs the interactive fixture-binding modal. Contains domain data only; no
    DOM locators (zero-locator rule).
    """

    model_config = ConfigDict(extra="forbid")

    target_app_url: str
    projects: list[InventoryProject] = Field(default_factory=list)


class ScenarioFixtureBinding(BaseModel):
    """A resolved binding of one fixture slot to a real 4ga element."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    target_app_url: str
    ref: str
    entity_kind: FixtureKind
    entity_id: str
    resolved_values: dict[str, object] = Field(default_factory=dict)
    created_by_specpilot: bool = False
    bound_at: str


class FixtureBindRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    ref: str
    mode: Literal["existing", "create"]
    kind: FixtureKind
    entity_id: str | None = None
    parent_id: str | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class FixtureSlotBindingState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    kind: FixtureKind
    bound: bool
    exists: bool
    binding: ScenarioFixtureBinding | None = None


class ScenarioBindingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    target_app_url: str
    data_dependency: DataDependency
    ready: bool
    slots: list[FixtureSlotBindingState] = Field(default_factory=list)
