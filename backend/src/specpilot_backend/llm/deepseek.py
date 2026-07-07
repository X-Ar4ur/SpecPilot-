from __future__ import annotations

from typing import Any, TypeVar

from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion
from langchain_core.messages import AIMessage, BaseMessage as LCBaseMessage
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel

from specpilot_backend.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


def build_deepseek_chat_model(
    *,
    settings: Settings | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ChatDeepSeek:
    resolved_settings = settings or get_settings()
    return ChatDeepSeek(
        model=resolved_settings.deepseek_model,
        api_key=resolved_settings.deepseek_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class LangChainDeepSeekBrowserUseModel:
    """Adapter from langchain-deepseek to browser-use's BaseChatModel protocol."""

    def __init__(self, chat_model: ChatDeepSeek) -> None:
        self.chat_model = chat_model
        self.model = chat_model.model_name
        self.model_name = chat_model.model_name
        self._verified_api_keys = False

    @property
    def provider(self) -> str:
        return "deepseek"

    @property
    def name(self) -> str:
        return self.model

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        output_format: type[T] | None = None,
        **_: Any,
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        langchain_messages = [_to_langchain_message(message) for message in messages]
        if output_format is None:
            result = await self.chat_model.ainvoke(langchain_messages)
            content = result.content if isinstance(result.content, str) else str(result.content)
            return ChatInvokeCompletion(completion=content, usage=None)

        structured = self.chat_model.with_structured_output(
            output_format,
            method="json_mode",
        )
        parsed = await structured.ainvoke(langchain_messages)
        if isinstance(parsed, output_format):
            completion = parsed
        else:
            completion = output_format.model_validate(parsed)
        return ChatInvokeCompletion(completion=completion, usage=None)


def build_browser_use_deepseek_model(
    *, settings: Settings | None = None
) -> LangChainDeepSeekBrowserUseModel:
    return LangChainDeepSeekBrowserUseModel(build_deepseek_chat_model(settings=settings))


def _to_langchain_message(message: BaseMessage) -> LCBaseMessage:
    content = _message_text(message)
    if message.role == "system":
        return SystemMessage(content=content)
    if message.role == "assistant":
        return AIMessage(content=content)
    return HumanMessage(content=content)


def _message_text(message: BaseMessage) -> str:
    if hasattr(message, "text"):
        return str(message.text)
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)
