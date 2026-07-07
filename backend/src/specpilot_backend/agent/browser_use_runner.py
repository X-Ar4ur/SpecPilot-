from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pydantic import SecretStr

from specpilot_backend.agent.task_builder import build_browser_use_task
from specpilot_backend.config import Settings, get_settings
from specpilot_backend.events.bus import get_event_bus
from specpilot_backend.ids import new_event_id
from specpilot_backend.llm.deepseek import build_browser_use_deepseek_model
from specpilot_backend.llm.openai_compatible import (
    build_browser_use_openai_compatible_model,
)
from specpilot_backend.models.events import TraceEvent
from specpilot_backend.models.scenarios import TestScenario


@dataclass(frozen=True)
class BrowserUseRunResult:
    success: bool | None
    final_result: str | None
    urls: list[str] = field(default_factory=list)
    action_names: list[str] = field(default_factory=list)
    screenshot_paths: list[str] = field(default_factory=list)
    errors: list[str | None] = field(default_factory=list)
    steps: int | None = None


def create_browser_session(settings: Settings | None = None) -> Any:
    resolved_settings = settings or get_settings()
    from browser_use import Browser

    return Browser(
        headless=resolved_settings.browser_headless,
        user_data_dir=None,
        allowed_domains=_effective_allowed_domains(resolved_settings),
    )


def build_sensitive_data(
    settings: Settings | None = None,
) -> dict[str, str | dict[str, str]]:
    resolved_settings = settings or get_settings()
    values: dict[str, str] = {}
    if resolved_settings.fourga_username:
        values["FOURGA_USERNAME"] = resolved_settings.fourga_username
    if resolved_settings.fourga_password:
        fourga_password = _secret_value(resolved_settings.fourga_password)
        if fourga_password is not None:
            values["FOURGA_PASSWORD"] = fourga_password
    if not values:
        return {}
    return {
        domain: dict(values)
        for domain in _effective_allowed_domains(resolved_settings)
        if domain != "*"
    }


def build_initial_actions(settings: Settings | None = None) -> list[dict[str, Any]]:
    resolved_settings = settings or get_settings()
    return [
        {
            "navigate": {
                "url": _normalize_target_app_url(resolved_settings.target_app_url),
                "new_tab": False,
            }
        }
    ]


def create_browser_use_llm(settings: Settings | None = None) -> Any:
    resolved_settings = settings or get_settings()
    if resolved_settings.text_llm_provider == "openai_compatible":
        return build_browser_use_openai_compatible_model(settings=resolved_settings)
    if resolved_settings.text_llm_provider == "browser_use":
        from browser_use import ChatBrowserUse

        api_key = _secret_value(resolved_settings.browser_use_api_key)
        if api_key is None:
            msg = "BROWSER_USE_API_KEY is required for Browser Use hosted LLM"
            raise ValueError(msg)
        return ChatBrowserUse(
            model=resolved_settings.browser_use_model,
            api_key=api_key,
        )
    return build_browser_use_deepseek_model(settings=resolved_settings)


async def run_scenario_with_browser_use(
    scenario: TestScenario,
    *,
    run_id: str,
    settings: Settings | None = None,
    publish_history_events: bool = True,
) -> BrowserUseRunResult:
    resolved_settings = settings or get_settings()
    sensitive_data = build_sensitive_data(resolved_settings) or None
    task = build_browser_use_task(
        scenario,
        target_app_url=_normalize_target_app_url(resolved_settings.target_app_url),
        include_login_guidance=sensitive_data is not None,
    )
    browser = create_browser_session(resolved_settings)
    llm = create_browser_use_llm(resolved_settings)

    from browser_use import Agent

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        sensitive_data=sensitive_data,
        initial_actions=build_initial_actions(resolved_settings),
    )
    history = await agent.run(
        max_steps=effective_max_steps(scenario, resolved_settings)
    )
    result = history_to_run_result(history)
    if publish_history_events:
        await _publish_history_events(run_id, result)
    return result


def run_scenario_with_browser_use_sync(
    scenario: TestScenario,
    *,
    run_id: str,
    settings: Settings | None = None,
) -> BrowserUseRunResult:
    return asyncio.run(
        run_scenario_with_browser_use(scenario, run_id=run_id, settings=settings)
    )


def effective_max_steps(scenario: TestScenario, settings: Settings) -> int:
    return max(scenario.max_steps, settings.max_scenario_steps)


def history_to_run_result(history: Any) -> BrowserUseRunResult:
    return BrowserUseRunResult(
        success=_call_history_method(history, "is_successful"),
        final_result=_call_history_method(history, "final_result"),
        urls=list(_call_history_method(history, "urls") or []),
        action_names=list(_call_history_method(history, "action_names") or []),
        screenshot_paths=list(_call_history_method(history, "screenshot_paths") or []),
        errors=list(_call_history_method(history, "errors") or []),
        steps=_call_history_method(history, "number_of_steps"),
    )


def _allowed_domains(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _effective_allowed_domains(settings: Settings) -> list[str]:
    domains = _allowed_domains(settings.browser_allowed_domains)
    target_origin = _target_origin(settings.target_app_url)
    if target_origin and not any(
        _domain_covers_origin(domain, target_origin) for domain in domains
    ):
        domains.append(target_origin)
    return domains


def _target_origin(target_app_url: str) -> str | None:
    normalized = _normalize_target_app_url(target_app_url)
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _normalize_target_app_url(target_app_url: str) -> str:
    value = target_app_url.strip()
    if "://" in value:
        return value
    host = value.split("/", 1)[0]
    scheme = "http" if _is_local_host(host) else "https"
    return f"{scheme}://{value}"


def _is_local_host(host: str) -> bool:
    return (
        host.startswith("localhost")
        or host.startswith("127.")
        or host.startswith("0.0.0.0")
        or host.startswith("[::1]")
    )


def _domain_covers_origin(domain: str, origin: str) -> bool:
    if domain == "*":
        return True
    parsed_origin = urlparse(origin)
    origin_host = parsed_origin.hostname or ""
    origin_netloc = parsed_origin.netloc
    domain_part = domain.split("://", 1)[-1].rstrip("/")
    if domain_part == origin_netloc or domain_part == origin_host:
        return True
    if domain_part.startswith("*."):
        suffix = domain_part[2:]
        return origin_host == suffix or origin_host.endswith(f".{suffix}")
    return False


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _call_history_method(history: Any, name: str) -> Any:
    method = getattr(history, name, None)
    if method is None:
        return None
    return method()


async def _publish_history_events(run_id: str, result: BrowserUseRunResult) -> None:
    bus = get_event_bus()
    for index, action_name in enumerate(result.action_names, start=1):
        await bus.publish(
            TraceEvent(
                event_id=new_event_id(),
                run_id=run_id,
                ts=_utc_now(),
                type="browser_step",
                node="BrowserUseRun",
                status="running",
                message=f"browser-use action {index}: {action_name}",
                payload={"step": index, "action": action_name},
            )
        )
    for index, screenshot_path in enumerate(result.screenshot_paths, start=1):
        await bus.publish(
            TraceEvent(
                event_id=new_event_id(),
                run_id=run_id,
                ts=_utc_now(),
                type="browser_frame",
                node="BrowserUseRun",
                status="running",
                message=f"browser frame {index}",
                payload={"frame_index": index, "screenshot_path": screenshot_path},
            )
        )


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
