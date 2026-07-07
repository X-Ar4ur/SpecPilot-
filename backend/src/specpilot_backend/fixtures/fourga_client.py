from __future__ import annotations

from typing import Any

import httpx

from specpilot_backend.config import Settings, get_settings
from specpilot_backend.fixtures.models import (
    FixtureInventory,
    InventoryBoard,
    InventoryCard,
    InventoryList,
    InventoryProject,
)

DEFAULT_CARD_POSITION = 65535


class FourgaApiError(Exception):
    """Raised when the 4ga Boards REST API returns an unexpected result."""


class FourgaApiClient:
    """Minimal client for the 4ga Boards (Planka-style) REST API.

    Used only for the Arrange phase (listing/creating fixture data). It never
    drives test execution or verification. The login token is held in memory and
    never logged, traced, or returned to the frontend.
    """

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

    async def list_inventory(self) -> FixtureInventory:
        """Assemble the Project -> Board -> List -> Card tree."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Authorization": f"Bearer {await self._login(client)}"}
            projects_payload = await self._get_json(client, "/api/projects", headers)
            boards_by_project = _group_boards_by_project(projects_payload)
            projects: list[InventoryProject] = []
            for project in _as_dict_list(projects_payload.get("items")):
                project_id = str(project.get("id", ""))
                boards: list[InventoryBoard] = []
                for board_stub in boards_by_project.get(project_id, []):
                    board_payload = await self._get_json(
                        client, f"/api/boards/{board_stub.get('id')}", headers
                    )
                    boards.append(_build_board(board_stub, board_payload))
                projects.append(
                    InventoryProject(
                        id=project_id,
                        name=str(project.get("name", "")),
                        boards=boards,
                    )
                )
            return FixtureInventory(target_app_url=self.base_url, projects=projects)

    async def create_card(
        self,
        *,
        list_id: str,
        title: str,
        position: float = DEFAULT_CARD_POSITION,
    ) -> str:
        """Create a card in a list and return its id."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Authorization": f"Bearer {await self._login(client)}"}
            response = await client.post(
                f"{self.base_url}/api/lists/{list_id}/cards",
                headers=headers,
                json={"name": title, "position": position},
            )
            response.raise_for_status()
            item = response.json().get("item")
            if not isinstance(item, dict) or item.get("id") is None:
                raise FourgaApiError("4ga card creation did not return an id")
            return str(item["id"])

    async def _login(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            f"{self.base_url}/api/access-tokens",
            json={"emailOrUsername": self.username, "password": self.password},
        )
        response.raise_for_status()
        token = response.json().get("item")
        if not isinstance(token, str) or not token:
            raise FourgaApiError("4ga login did not return an access token")
        return token

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        path: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        response = await client.get(f"{self.base_url}{path}", headers=headers)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise FourgaApiError(f"4ga {path} returned a non-object payload")
        return payload


def resolve_target_base_url(settings: Settings | None = None) -> str:
    """Resolve the 4ga API base URL: FOURGA_API_BASE_URL or target_app_url."""
    resolved = settings or get_settings()
    base = resolved.fourga_api_base_url or resolved.target_app_url
    return base.rstrip("/")


def build_fourga_client(settings: Settings | None = None) -> FourgaApiClient | None:
    """Build a client from settings, or None when credentials are missing."""
    resolved = settings or get_settings()
    if resolved.fourga_username is None or resolved.fourga_password is None:
        return None
    return FourgaApiClient(
        base_url=resolve_target_base_url(resolved),
        username=resolved.fourga_username,
        password=resolved.fourga_password.get_secret_value(),
    )


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _included(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    included = payload.get("included")
    if isinstance(included, dict):
        return _as_dict_list(included.get(key))
    return []


def _group_boards_by_project(
    projects_payload: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for board in _included(projects_payload, "boards"):
        grouped.setdefault(str(board.get("projectId", "")), []).append(board)
    return grouped


def _build_board(
    board_stub: dict[str, Any], board_payload: dict[str, Any]
) -> InventoryBoard:
    item = board_payload.get("item")
    item_name = item.get("name") if isinstance(item, dict) else None
    name = str(item_name or board_stub.get("name", ""))

    cards_by_list: dict[str, list[InventoryCard]] = {}
    for card in _included(board_payload, "cards"):
        cards_by_list.setdefault(str(card.get("listId", "")), []).append(
            InventoryCard(id=str(card.get("id", "")), name=str(card.get("name", "")))
        )

    lists = [
        InventoryList(
            id=str(lst.get("id", "")),
            name=str(lst.get("name", "")),
            cards=cards_by_list.get(str(lst.get("id", "")), []),
        )
        for lst in _included(board_payload, "lists")
    ]
    return InventoryBoard(id=str(board_stub.get("id", "")), name=name, lists=lists)
