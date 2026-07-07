from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from specpilot_backend.config import Settings
from specpilot_backend.fixtures import binding_service
from specpilot_backend.fixtures.binding_service import (
    FixtureBindError,
    FixtureNotConfiguredError,
    ScenarioNotFoundError,
    bind_slot,
    get_binding_status,
)
from specpilot_backend.fixtures.models import (
    FixtureBindRequest,
    FixtureInventory,
    InventoryBoard,
    InventoryCard,
    InventoryList,
    InventoryProject,
)
from specpilot_backend.main import app
from specpilot_backend.services import persistence

TARGET = "http://localhost:1337"

INVENTORY = FixtureInventory(
    target_app_url=TARGET,
    projects=[
        InventoryProject(
            id="1",
            name="p",
            boards=[
                InventoryBoard(
                    id="10",
                    name="b",
                    lists=[
                        InventoryList(
                            id="100",
                            name="To Do",
                            cards=[InventoryCard(id="1000", name="完成季度报告")],
                        )
                    ],
                )
            ],
        )
    ],
)


def _settings(db: Path, *, creds: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{db}",
        fourga_username="demo" if creds else None,
        fourga_password="demo" if creds else None,
        fourga_api_base_url=TARGET,
    )


def _save_scenario(
    scenario_id: str,
    fixtures: list[dict[str, object]],
    data_dependency: str = "interactive",
    **extra: object,
) -> None:
    payload: dict[str, object] = {
        "scenario_id": scenario_id,
        "feature_id": "ft1",
        "review_status": "auto_validated",
        "priority": "P0",
        "difficulty": "simple",
        "is_mutation": False,
        "title": "t",
        "data_dependency": data_dependency,
        "fixtures": fixtures,
    }
    payload.update(extra)
    persistence.save_scenario_payload(payload)


class FakeCreateClient:
    def __init__(self) -> None:
        self.last: tuple[str, str] | None = None

    async def create_card(self, *, list_id: str, title: str) -> str:
        self.last = (list_id, title)
        return "2000"


class FakeInventoryClient:
    async def list_inventory(self) -> FixtureInventory:
        return INVENTORY


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "specpilot.db"
    persistence.configure_database(f"sqlite:///{path}")
    persistence.create_tables()
    return path


# --- persistence -----------------------------------------------------------


def test_binding_persistence_isolated_per_instance(db: Path) -> None:
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc1",
            "target_app_url": "http://a",
            "ref": "target_card",
            "entity_kind": "card",
            "entity_id": "100",
            "resolved_values": {"title": "X"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc1",
            "target_app_url": "http://b",
            "ref": "target_card",
            "entity_kind": "card",
            "entity_id": "200",
            "resolved_values": {"title": "Y"},
            "created_by_specpilot": True,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )

    a = persistence.get_fixture_binding("sc1", "http://a", "target_card")
    assert a is not None
    assert a["entity_id"] == "100"
    assert a["resolved_values"] == {"title": "X"}

    b_list = persistence.list_fixture_bindings("sc1", "http://b")
    assert len(b_list) == 1
    assert b_list[0]["entity_id"] == "200"


# --- bind_slot -------------------------------------------------------------


@pytest.mark.anyio
async def test_bind_existing_persists_binding(db: Path) -> None:
    request = FixtureBindRequest(
        scenario_id="sc1",
        ref="target_card",
        mode="existing",
        kind="card",
        entity_id="1000",
        attributes={"title": "完成季度报告"},
    )

    binding = await bind_slot(request, settings=_settings(db))

    assert binding.entity_id == "1000"
    assert binding.created_by_specpilot is False
    assert binding.resolved_values == {"title": "完成季度报告"}
    assert binding.target_app_url == TARGET
    stored = persistence.get_fixture_binding("sc1", TARGET, "target_card")
    assert stored is not None
    assert stored["entity_id"] == "1000"


@pytest.mark.anyio
async def test_bind_create_calls_client_and_marks_created(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeCreateClient()
    monkeypatch.setattr(binding_service, "build_fourga_client", lambda _=None: fake)
    request = FixtureBindRequest(
        scenario_id="sc1",
        ref="target_card",
        mode="create",
        kind="card",
        parent_id="100",
        attributes={"title": "完成季度报告"},
    )

    binding = await bind_slot(request, settings=_settings(db))

    assert binding.entity_id == "2000"
    assert binding.created_by_specpilot is True
    assert fake.last == ("100", "完成季度报告")


@pytest.mark.anyio
async def test_bind_existing_requires_entity_id(db: Path) -> None:
    request = FixtureBindRequest(
        scenario_id="s", ref="r", mode="existing", kind="card"
    )

    with pytest.raises(FixtureBindError):
        await bind_slot(request, settings=_settings(db))


@pytest.mark.anyio
async def test_bind_create_rejects_non_card_kind(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(binding_service, "build_fourga_client", lambda _=None: object())
    request = FixtureBindRequest(
        scenario_id="s",
        ref="r",
        mode="create",
        kind="list",
        parent_id="1",
        attributes={"title": "x"},
    )

    with pytest.raises(FixtureBindError):
        await bind_slot(request, settings=_settings(db))


@pytest.mark.anyio
async def test_bind_create_not_configured_raises(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(binding_service, "build_fourga_client", lambda _=None: None)
    request = FixtureBindRequest(
        scenario_id="s",
        ref="r",
        mode="create",
        kind="card",
        parent_id="1",
        attributes={"title": "x"},
    )

    with pytest.raises(FixtureNotConfiguredError):
        await bind_slot(request, settings=_settings(db, creds=False))


# --- get_binding_status ----------------------------------------------------


@pytest.mark.anyio
async def test_binding_status_no_fixtures_is_ready(db: Path) -> None:
    _save_scenario("sc_none", [], data_dependency="none")

    status = await get_binding_status("sc_none", settings=_settings(db))

    assert status.ready is True
    assert status.slots == []


@pytest.mark.anyio
async def test_binding_status_unknown_scenario_raises(db: Path) -> None:
    with pytest.raises(ScenarioNotFoundError):
        await get_binding_status("missing", settings=_settings(db))


@pytest.mark.anyio
async def test_binding_status_existing_present_is_ready(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save_scenario("sc_fx", [{"ref": "target_card", "kind": "card"}])
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc_fx",
            "target_app_url": TARGET,
            "ref": "target_card",
            "entity_kind": "card",
            "entity_id": "1000",
            "resolved_values": {"title": "完成季度报告"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(
        binding_service, "build_fourga_client", lambda _=None: FakeInventoryClient()
    )

    status = await get_binding_status("sc_fx", settings=_settings(db))

    assert status.ready is True
    assert status.slots[0].bound is True
    assert status.slots[0].exists is True


@pytest.mark.anyio
async def test_binding_status_missing_element_not_ready(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save_scenario("sc_fx2", [{"ref": "target_card", "kind": "card"}])
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc_fx2",
            "target_app_url": TARGET,
            "ref": "target_card",
            "entity_kind": "card",
            "entity_id": "9999",
            "resolved_values": {"title": "X"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(
        binding_service, "build_fourga_client", lambda _=None: FakeInventoryClient()
    )

    status = await get_binding_status("sc_fx2", settings=_settings(db))

    assert status.ready is False
    assert status.slots[0].bound is True
    assert status.slots[0].exists is False


@pytest.mark.anyio
async def test_binding_status_incomplete_attributes_not_ready(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save_scenario(
        "sc_attr",
        [{"ref": "target_card", "kind": "card"}],
        test_data={
            "a": "{{fixture.target_card.title}}",
            "b": "{{fixture.target_card.list_name}}",
        },
    )
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc_attr",
            "target_app_url": TARGET,
            "ref": "target_card",
            "entity_kind": "card",
            "entity_id": "1000",
            "resolved_values": {"title": "完成季度报告"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(
        binding_service, "build_fourga_client", lambda _=None: FakeInventoryClient()
    )

    status = await get_binding_status("sc_attr", settings=_settings(db))

    assert status.ready is False
    assert status.slots[0].bound is True
    assert status.slots[0].exists is False


@pytest.mark.anyio
async def test_binding_status_complete_attributes_ready(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save_scenario(
        "sc_attr2",
        [{"ref": "target_card", "kind": "card"}],
        test_data={
            "a": "{{fixture.target_card.title}}",
            "b": "{{fixture.target_card.list_name}}",
        },
    )
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc_attr2",
            "target_app_url": TARGET,
            "ref": "target_card",
            "entity_kind": "card",
            "entity_id": "1000",
            "resolved_values": {"title": "完成季度报告", "list_name": "To Do"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(
        binding_service, "build_fourga_client", lambda _=None: FakeInventoryClient()
    )

    status = await get_binding_status("sc_attr2", settings=_settings(db))

    assert status.ready is True
    assert status.slots[0].exists is True


@pytest.mark.anyio
async def test_binding_status_accepts_legacy_title_token_for_board(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save_scenario(
        "sc_legacy_board_title",
        [{"ref": "target_board", "kind": "board"}],
        test_data={"board_name": "{{fixture.target_board.title}}"},
    )
    persistence.save_fixture_binding(
        {
            "scenario_id": "sc_legacy_board_title",
            "target_app_url": TARGET,
            "ref": "target_board",
            "entity_kind": "board",
            "entity_id": "10",
            "resolved_values": {"name": "b", "project_name": "p"},
            "created_by_specpilot": False,
            "bound_at": "2026-06-18T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(
        binding_service, "build_fourga_client", lambda _=None: FakeInventoryClient()
    )

    status = await get_binding_status(
        "sc_legacy_board_title", settings=_settings(db)
    )

    assert status.ready is True
    assert status.slots[0].exists is True


# --- HTTP routes -----------------------------------------------------------


@pytest.fixture
def client(db: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = _settings(db)
    monkeypatch.setattr(
        "specpilot_backend.api.settings.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "specpilot_backend.fixtures.binding_service.get_settings", lambda: settings
    )
    with TestClient(app) as test_client:
        yield test_client


def test_bind_endpoint_existing(client: TestClient) -> None:
    response = client.post(
        "/api/fixtures/bind",
        json={
            "scenario_id": "sc1",
            "ref": "target_card",
            "mode": "existing",
            "kind": "card",
            "entity_id": "1000",
            "attributes": {"title": "完成季度报告"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == "1000"
    assert body["created_by_specpilot"] is False
    assert body["target_app_url"] == TARGET


def test_binding_status_endpoint_no_fixtures(client: TestClient) -> None:
    _save_scenario("sc_http_none", [], data_dependency="none")

    response = client.get("/api/scenarios/sc_http_none/binding")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_binding_status_endpoint_unknown_returns_404(client: TestClient) -> None:
    response = client.get("/api/scenarios/missing/binding")

    assert response.status_code == 404
