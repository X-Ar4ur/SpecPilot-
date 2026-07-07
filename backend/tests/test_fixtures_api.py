from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from specpilot_backend.config import Settings
from specpilot_backend.fixtures.fourga_client import FourgaApiError
from specpilot_backend.fixtures.models import (
    FixtureInventory,
    InventoryBoard,
    InventoryCard,
    InventoryList,
    InventoryProject,
)
from specpilot_backend.main import app
from specpilot_backend.services import persistence

INVENTORY = FixtureInventory(
    target_app_url="http://localhost:1337",
    projects=[
        InventoryProject(
            id="1",
            name="Getting started",
            boards=[
                InventoryBoard(
                    id="10",
                    name="Learn 4ga",
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


class FakeClient:
    def __init__(
        self,
        inventory: FixtureInventory = INVENTORY,
        error: Exception | None = None,
    ) -> None:
        self._inventory = inventory
        self._error = error

    async def list_inventory(self) -> FixtureInventory:
        if self._error is not None:
            raise self._error
        return self._inventory


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    tmp_path = Path(".pytest_cache") / "specpilot-tests" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
    )
    monkeypatch.setattr("specpilot_backend.api.settings.get_settings", lambda: settings)
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    with TestClient(app) as test_client:
        yield test_client


def test_inventory_returns_tree(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "specpilot_backend.api.fixtures.build_fourga_client",
        lambda: FakeClient(),
    )

    response = client.get("/api/fixtures/inventory")

    assert response.status_code == 200
    body = response.json()
    card = body["projects"][0]["boards"][0]["lists"][0]["cards"][0]
    assert card == {"id": "1000", "name": "完成季度报告"}


def test_inventory_not_configured_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "specpilot_backend.api.fixtures.build_fourga_client",
        lambda: None,
    )

    response = client.get("/api/fixtures/inventory")

    assert response.status_code == 503


def test_inventory_upstream_error_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "specpilot_backend.api.fixtures.build_fourga_client",
        lambda: FakeClient(error=FourgaApiError("boom")),
    )

    response = client.get("/api/fixtures/inventory")

    assert response.status_code == 502
