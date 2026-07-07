from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

import httpx
from browser_use.llm.views import ChatInvokeCompletion
from pydantic import BaseModel

from specpilot_backend.config import Settings, get_settings

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class OpenAICompatibleBrowserUseModel:
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> None:
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.model_name = model
        self.temperature = temperature
        self.timeout = timeout

    @property
    def provider(self) -> str:
        return "openai_compatible"

    @property
    def name(self) -> str:
        return self.model

    async def ainvoke(
        self,
        messages: Sequence[Any],
        output_format: type[StructuredOutput] | None = None,
        **_: Any,
    ) -> ChatInvokeCompletion[str] | ChatInvokeCompletion[StructuredOutput]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_payload(message) for message in messages],
            "temperature": self.temperature,
        }
        if output_format is not None:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if output_format is None:
            return ChatInvokeCompletion(completion=content, usage=None)
        return ChatInvokeCompletion(
            completion=output_format.model_validate_json(content),
            usage=None,
        )


def build_browser_use_openai_compatible_model(
    settings: Settings | None = None,
) -> OpenAICompatibleBrowserUseModel:
    resolved_settings = settings or get_settings()
    if resolved_settings.openai_compatible_api_key is None:
        msg = "OPENAI_COMPATIBLE_API_KEY is required for OpenAI-compatible LLM"
        raise ValueError(msg)
    return OpenAICompatibleBrowserUseModel(
        provider_name=resolved_settings.openai_compatible_provider_name,
        base_url=resolved_settings.openai_compatible_base_url,
        api_key=resolved_settings.openai_compatible_api_key.get_secret_value(),
        model=resolved_settings.openai_compatible_model,
    )


def _message_to_payload(message: Any) -> dict[str, str]:
    role = getattr(message, "role", "user")
    text = getattr(message, "text", None)
    if text is None:
        text = getattr(message, "content", "")
    return {"role": str(role), "content": str(text)}
