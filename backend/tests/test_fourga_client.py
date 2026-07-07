from __future__ import annotations

from typing import Any

import pytest

from specpilot_backend.config import Settings
from specpilot_backend.fixtures.fourga_client import (
    FourgaApiClient,
    FourgaApiError,
    build_fourga_client,
)

BASE = "http://localhost:1337"

PROJECTS_PAYLOAD = {
    "items": [{"id": 1, "name": "Getting started"}],
    "included": {"boards": [{"id": 10, "name": "Learn 4ga", "projectId": 1}]},
}
BOARD_PAYLOAD = {
    "item": {"id": 10, "name": "Learn 4ga", "projectId": 1},
    "included": {
        "lists": [
            {"id": 100, "name": "To Do", "boardId": 10},
            {"id": 101, "name": "Done", "boardId": 10},
        ],
        "cards": [
            {"id": 1000, "name": "完成季度报告", "listId": 100},
            {"id": 1001, "name": "买菜清单", "listId": 100},
            {"id": 1002, "name": "归档", "listId": 101},
        ],
    },
}


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class FakeAsyncClient:
    requests: list[dict[str, Any]] = []
    login_item: object = "fake-jwt-token"

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        FakeAsyncClient.requests.append(
            {"method": "POST", "url": url, "json": json, "headers": headers}
        )
        if url.endswith("/api/access-tokens"):
            return FakeResponse({"item": FakeAsyncClient.login_item})
        if url.endswith("/cards"):
            return FakeResponse({"item": {"id": 2000, "name": json["name"]}})
        raise AssertionError(f"unexpected POST {url}")

    async def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        FakeAsyncClient.requests.append(
            {"method": "GET", "url": url, "headers": headers}
        )
        if url.endswith("/api/projects"):
            return FakeResponse(PROJECTS_PAYLOAD)
        if "/api/boards/" in url:
            return FakeResponse(BOARD_PAYLOAD)
        raise AssertionError(f"unexpected GET {url}")


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[FakeAsyncClient]:
    FakeAsyncClient.requests = []
    FakeAsyncClient.login_item = "fake-jwt-token"
    monkeypatch.setattr(
        "specpilot_backend.fixtures.fourga_client.httpx.AsyncClient",
        FakeAsyncClient,
    )
    return FakeAsyncClient


def _client() -> FourgaApiClient:
    return FourgaApiClient(base_url=BASE, username="demo", password="demo")


@pytest.mark.anyio
async def test_list_inventory_assembles_tree(
    fake_http: type[FakeAsyncClient],
) -> None:
    inventory = await _client().list_inventory()

    assert inventory.target_app_url == BASE
    assert [p.name for p in inventory.projects] == ["Getting started"]
    board = inventory.projects[0].boards[0]
    assert board.name == "Learn 4ga"
    assert [lst.name for lst in board.lists] == ["To Do", "Done"]
    assert [c.name for c in board.lists[0].cards] == ["完成季度报告", "买菜清单"]
    assert [c.name for c in board.lists[1].cards] == ["归档"]
    assert board.lists[0].cards[0].id == "1000"


@pytest.mark.anyio
async def test_list_inventory_logs_in_with_bearer(
    fake_http: type[FakeAsyncClient],
) -> None:
    await _client().list_inventory()

    login = [r for r in fake_http.requests if r["url"].endswith("/api/access-tokens")]
    assert login[0]["json"] == {"emailOrUsername": "demo", "password": "demo"}
    gets = [r for r in fake_http.requests if r["method"] == "GET"]
    assert gets and all(
        r["headers"]["Authorization"] == "Bearer fake-jwt-token" for r in gets
    )


@pytest.mark.anyio
async def test_create_card_posts_name_and_position(
    fake_http: type[FakeAsyncClient],
) -> None:
    card_id = await _client().create_card(list_id="100", title="完成季度报告")

    assert card_id == "2000"
    post = next(
        r for r in fake_http.requests if r["method"] == "POST" and r["url"].endswith("/cards")
    )
    assert post["url"] == f"{BASE}/api/lists/100/cards"
    assert post["json"]["name"] == "完成季度报告"
    assert "position" in post["json"]
    assert post["headers"]["Authorization"] == "Bearer fake-jwt-token"


@pytest.mark.anyio
async def test_login_without_token_raises(
    fake_http: type[FakeAsyncClient],
) -> None:
    fake_http.login_item = None
    with pytest.raises(FourgaApiError, match="access token"):
        await _client().list_inventory()


def test_build_fourga_client_requires_credentials() -> None:
    settings = Settings(_env_file=None, fourga_username=None, fourga_password=None)

    assert build_fourga_client(settings=settings) is None


def test_build_fourga_client_prefers_api_base_url() -> None:
    settings = Settings(
        _env_file=None,
        fourga_username="demo",
        fourga_password="demo",
        fourga_api_base_url="http://localhost:1337",
        target_app_url="http://localhost:3000/",
    )

    client = build_fourga_client(settings=settings)

    assert client is not None
    assert client.base_url == "http://localhost:1337"


def test_build_fourga_client_falls_back_to_target_app_url() -> None:
    settings = Settings(
        _env_file=None,
        fourga_username="demo",
        fourga_password="demo",
        fourga_api_base_url=None,
        target_app_url="http://localhost:1337/",
    )

    client = build_fourga_client(settings=settings)

    assert client is not None
    assert client.base_url == "http://localhost:1337"
