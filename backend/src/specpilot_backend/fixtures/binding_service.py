from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from specpilot_backend.config import Settings, get_settings
from specpilot_backend.fixtures.fourga_client import (
    build_fourga_client,
    resolve_target_base_url,
)
from specpilot_backend.fixtures.models import (
    FixtureBindRequest,
    FixtureInventory,
    FixtureSlotBindingState,
    ScenarioBindingStatus,
    ScenarioFixtureBinding,
)
from specpilot_backend.fixtures.tokens import (
    find_fixture_tokens,
    resolve_fixture_tokens,
    unresolved_fixture_tokens,
)
from specpilot_backend.models.scenarios import DataDependency, FixtureSlot
from specpilot_backend.services.persistence import (
    get_fixture_binding,
    get_scenario_payload,
    list_fixture_bindings,
    save_fixture_binding,
)


class FixtureNotConfiguredError(Exception):
    """The target 4ga instance is not configured (missing credentials)."""


class FixtureBindError(ValueError):
    """The bind request is invalid."""


class ScenarioNotFoundError(Exception):
    """No scenario exists with the requested id."""


class FixturePreconditionError(Exception):
    """A data-dependent scenario could not be resolved before execution."""

    def __init__(self, message: str, unresolved_refs: list[str]) -> None:
        super().__init__(message)
        self.unresolved_refs = unresolved_refs


async def bind_slot(
    request: FixtureBindRequest, *, settings: Settings | None = None
) -> ScenarioFixtureBinding:
    """Bind one fixture slot to an existing or newly created element."""
    resolved_settings = settings or get_settings()
    target = resolve_target_base_url(resolved_settings)

    if request.mode == "existing":
        if not request.entity_id:
            raise FixtureBindError("existing binding requires entity_id")
        entity_id = request.entity_id
        created = False
    else:
        client = build_fourga_client(resolved_settings)
        if client is None:
            raise FixtureNotConfiguredError(
                "4ga target instance is not configured"
            )
        if request.kind != "card":
            raise FixtureBindError(
                "create mode supports kind 'card' only in the MVP"
            )
        if not request.parent_id:
            raise FixtureBindError("create mode requires parent_id (list id)")
        title = request.attributes.get("title")
        if not isinstance(title, str) or not title:
            raise FixtureBindError("create mode requires attributes.title")
        entity_id = await client.create_card(
            list_id=request.parent_id, title=title
        )
        created = True

    binding = ScenarioFixtureBinding(
        scenario_id=request.scenario_id,
        target_app_url=target,
        ref=request.ref,
        entity_kind=request.kind,
        entity_id=entity_id,
        resolved_values=_resolved_values_for_kind(request.kind, request.attributes),
        created_by_specpilot=created,
        bound_at=datetime.now(UTC).isoformat(),
    )
    save_fixture_binding(binding.model_dump())
    return binding


async def get_binding_status(
    scenario_id: str, *, settings: Settings | None = None
) -> ScenarioBindingStatus:
    """Report per-slot binding state, including a live existence check."""
    resolved_settings = settings or get_settings()
    target = resolve_target_base_url(resolved_settings)
    scenario = get_scenario_payload(scenario_id)
    if scenario is None:
        raise ScenarioNotFoundError(scenario_id)

    raw_fixtures = scenario.get("fixtures", [])
    slots = [
        FixtureSlot.model_validate(slot)
        for slot in (raw_fixtures if isinstance(raw_fixtures, list) else [])
    ]
    data_dependency = cast(
        DataDependency, scenario.get("data_dependency", "none")
    )

    if not slots:
        return ScenarioBindingStatus(
            scenario_id=scenario_id,
            target_app_url=target,
            data_dependency=data_dependency,
            ready=True,
            slots=[],
        )

    bindings_by_ref: dict[str, ScenarioFixtureBinding] = {}
    for slot in slots:
        binding_payload = get_fixture_binding(scenario_id, target, slot.ref)
        if binding_payload is not None:
            bindings_by_ref[slot.ref] = ScenarioFixtureBinding.model_validate(
                binding_payload
            )

    required_attrs_by_ref: dict[str, set[str]] = {}
    for ref, attr in find_fixture_tokens(scenario):
        required_attrs_by_ref.setdefault(ref, set()).add(attr)

    existing_ids = (
        await _existing_entity_ids(resolved_settings) if bindings_by_ref else set()
    )
    slot_states: list[FixtureSlotBindingState] = []
    for slot in slots:
        binding = bindings_by_ref.get(slot.ref)
        binding_values = (
            _resolved_values_for_kind(slot.kind, binding.resolved_values)
            if binding is not None
            else {}
        )
        display_binding = (
            binding.model_copy(update={"resolved_values": binding_values})
            if binding is not None
            else None
        )
        entity_present = binding is not None and binding.entity_id in existing_ids
        attrs_present = binding is not None and required_attrs_by_ref.get(
            slot.ref, set()
        ) <= set(binding_values.keys())
        slot_states.append(
            FixtureSlotBindingState(
                ref=slot.ref,
                kind=slot.kind,
                bound=binding is not None,
                exists=entity_present and attrs_present,
                binding=display_binding,
            )
        )

    return ScenarioBindingStatus(
        scenario_id=scenario_id,
        target_app_url=target,
        data_dependency=data_dependency,
        ready=all(state.exists for state in slot_states),
        slots=slot_states,
    )


async def _existing_entity_ids(settings: Settings) -> set[str]:
    client = build_fourga_client(settings)
    if client is None:
        raise FixtureNotConfiguredError("4ga target instance is not configured")
    return _flatten_entity_ids(await client.list_inventory())


def _flatten_entity_ids(inventory: FixtureInventory) -> set[str]:
    ids: set[str] = set()
    for project in inventory.projects:
        ids.add(project.id)
        for board in project.boards:
            ids.add(board.id)
            for fixture_list in board.lists:
                ids.add(fixture_list.id)
                for card in fixture_list.cards:
                    ids.add(card.id)
    return ids


async def collect_unready_bindings(
    scenario_ids: list[str], *, settings: Settings | None = None
) -> list[dict[str, object]]:
    """Return one entry per scenario whose interactive fixtures are not ready."""
    resolved_settings = settings or get_settings()
    unready: list[dict[str, object]] = []
    for scenario_id in scenario_ids:
        try:
            status = await get_binding_status(
                scenario_id, settings=resolved_settings
            )
        except ScenarioNotFoundError:
            continue
        if not status.ready:
            unready.append(
                {
                    "scenario_id": scenario_id,
                    "data_dependency": status.data_dependency,
                    "slots": [
                        state.model_dump()
                        for state in status.slots
                        if not state.exists
                    ],
                }
            )
    return unready


def resolve_scenario_fixtures(
    scenario_payload: dict[str, object], *, settings: Settings | None = None
) -> dict[str, object]:
    """Replace fixture tokens with bound values for interactive scenarios.

    Raises :class:`FixturePreconditionError` when a required slot has no binding
    or a token cannot be resolved.
    """
    data_dependency = scenario_payload.get("data_dependency", "none")
    raw_fixtures = scenario_payload.get("fixtures", [])
    fixtures = raw_fixtures if isinstance(raw_fixtures, list) else []
    if data_dependency != "interactive" or not fixtures:
        return scenario_payload

    resolved_settings = settings or get_settings()
    target = resolve_target_base_url(resolved_settings)
    scenario_id = str(scenario_payload.get("scenario_id", ""))
    resolved: dict[str, Mapping[str, object]] = {
        str(binding["ref"]): _as_mapping(binding.get("resolved_values"))
        for binding in list_fixture_bindings(scenario_id, target)
    }
    slot_refs = {
        str(slot["ref"])
        for slot in fixtures
        if isinstance(slot, dict) and "ref" in slot
    }
    kind_by_ref = {
        str(slot["ref"]): str(slot.get("kind", ""))
        for slot in fixtures
        if isinstance(slot, dict) and "ref" in slot
    }
    resolved = {
        ref: _resolved_values_for_kind(kind_by_ref.get(ref, ""), values)
        for ref, values in resolved.items()
    }
    resolved_payload = resolve_fixture_tokens(scenario_payload, resolved)
    leftover = {ref for ref, _ in unresolved_fixture_tokens(resolved_payload, resolved)}
    missing = sorted((slot_refs - set(resolved)) | leftover)
    if missing:
        raise FixturePreconditionError(
            f"unresolved fixture slots: {', '.join(missing)}", missing
        )
    return cast("dict[str, object]", resolved_payload)


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _resolved_values_for_kind(
    kind: str, values: Mapping[str, object]
) -> dict[str, object]:
    resolved = dict(values)
    if kind in {"project", "board", "list"}:
        display_name = _string_value(resolved.get("name")) or _string_value(
            resolved.get("title")
        )
        if display_name is not None:
            resolved.setdefault("name", display_name)
            resolved.setdefault("title", display_name)
            resolved.setdefault("middle_text", display_name)
    return resolved


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
