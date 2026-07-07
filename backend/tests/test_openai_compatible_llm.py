from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from specpilot_backend.config import Settings
from specpilot_backend.llm.openai_compatible import (
    OpenAICompatibleBrowserUseModel,
    build_browser_use_openai_compatible_model,
)


class FakeMessage:
    def __init__(self, role: str, text: str) -> None:
        self.role = role
        self.text = text


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeAsyncClient:
    requests: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return FakeResponse(
            {"choices": [{"message": {"content": '{"answer":"ok"}'}}]}
        )


class StructuredAnswer(BaseModel):
    answer: str


def test_openai_compatible_model_exposes_browser_use_model_name() -> None:
    model = OpenAICompatibleBrowserUseModel(
        provider_name="Clauddy",
        base_url="https://clauddy.com/v1",
        api_key="secret-key",
        model="gpt-5.5",
    )

    assert model.model_name == "gpt-5.5"
    assert model.name == "gpt-5.5"


@pytest.mark.anyio
async def test_openai_compatible_model_posts_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.requests = []
    monkeypatch.setattr(
        "specpilot_backend.llm.openai_compatible.httpx.AsyncClient",
        FakeAsyncClient,
    )
    model = OpenAICompatibleBrowserUseModel(
        provider_name="Clauddy",
        base_url="https://clauddy.com/v1/",
        api_key="secret-key",
        model="gpt-5.5",
    )

    result = await model.ainvoke(
        [
            FakeMessage("system", "You are helpful."),
            FakeMessage("user", "Say ok."),
        ]
    )

    assert result.completion == '{"answer":"ok"}'
    assert FakeAsyncClient.requests == [
        {
            "url": "https://clauddy.com/v1/chat/completions",
            "headers": {"Authorization": "Bearer secret-key"},
            "json": {
                "model": "gpt-5.5",
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Say ok."},
                ],
                "temperature": 0.0,
            },
        }
    ]


@pytest.mark.anyio
async def test_openai_compatible_model_ignores_browser_use_runtime_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.requests = []
    monkeypatch.setattr(
        "specpilot_backend.llm.openai_compatible.httpx.AsyncClient",
        FakeAsyncClient,
    )
    model = OpenAICompatibleBrowserUseModel(
        provider_name="Clauddy",
        base_url="https://clauddy.com/v1",
        api_key="secret-key",
        model="gpt-5.5",
    )

    result = await model.ainvoke(
        [FakeMessage("user", "Say ok.")],
        session_id="run_123",
    )

    assert result.completion == '{"answer":"ok"}'


@pytest.mark.anyio
async def test_openai_compatible_model_parses_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.requests = []
    monkeypatch.setattr(
        "specpilot_backend.llm.openai_compatible.httpx.AsyncClient",
        FakeAsyncClient,
    )
    model = OpenAICompatibleBrowserUseModel(
        provider_name="Clauddy",
        base_url="https://clauddy.com/v1",
        api_key="secret-key",
        model="gpt-5.5",
    )

    result = await model.ainvoke(
        [FakeMessage("user", "Return JSON.")],
        output_format=StructuredAnswer,
    )

    assert result.completion == StructuredAnswer(answer="ok")
    assert FakeAsyncClient.requests[0]["json"]["response_format"] == {
        "type": "json_object"
    }


def test_build_openai_compatible_model_requires_api_key() -> None:
    settings = Settings(
        _env_file=None,
        text_llm_provider="deepseek",
        openai_compatible_api_key=None,
    )

    with pytest.raises(ValueError, match="OPENAI_COMPATIBLE_API_KEY"):
        build_browser_use_openai_compatible_model(settings=settings)
