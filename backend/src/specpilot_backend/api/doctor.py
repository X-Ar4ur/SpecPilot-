from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text
from sqlmodel import Session

from specpilot_backend.config import get_settings
from specpilot_backend.generation.validators import (
    ZeroLocatorValidationError,
    validate_zero_locator_payload,
)
from specpilot_backend.services import persistence

router = APIRouter(prefix="/api/doctor", tags=["doctor"])

CheckStatus = Literal["ok", "warning", "error"]


def _check(status: CheckStatus, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def _overall_status(checks: dict[str, dict[str, str]]) -> CheckStatus:
    statuses = {check["status"] for check in checks.values()}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


@router.get("")
def get_doctor() -> dict[str, object]:
    try:
        settings = get_settings()
    except Exception as exc:  # pragma: no cover - defensive startup diagnostics
        checks = {
            "configuration": _check("error", f"settings invalid: {exc}"),
        }
        return {"status": "error", "checks": checks}

    checks: dict[str, dict[str, str]] = {
        "text_llm_provider": _check("ok", settings.text_llm_provider),
        "openai_compatible_api": _openai_compatible_check(
            selected=settings.text_llm_provider == "openai_compatible",
            provider_name=settings.openai_compatible_provider_name,
            base_url=settings.openai_compatible_base_url,
            model=settings.openai_compatible_model,
            configured=settings.openai_compatible_api_key is not None,
        ),
        "deepseek_api": _provider_key_check(
            selected=settings.text_llm_provider == "deepseek",
            configured=settings.deepseek_api_key is not None,
            configured_detail=f"key configured for {settings.deepseek_model}",
            missing_detail=f"missing DEEPSEEK_API_KEY for {settings.deepseek_model}",
            unselected_detail="not selected",
        ),
        "browser_use_llm": _provider_key_check(
            selected=(
                settings.text_llm_provider == "browser_use"
                or settings.browser_use_llm_fallback_enabled
            ),
            configured=settings.browser_use_api_key is not None,
            configured_detail=f"key configured for {settings.browser_use_model}",
            missing_detail="missing BROWSER_USE_API_KEY for selected hosted LLM",
            unselected_detail="not selected",
        ),
        "browser_use_cloud_browser": _check("ok", "disabled for MVP"),
        "glm_vision_api": _key_check(
            settings.glm_api_key is not None,
            "key configured",
            f"missing GLM_API_KEY for {settings.glm_vision_model}",
        ),
        "browser_use": _package_check("browser-use"),
        "database": _database_check(),
        "chroma": _writable_dir_check(settings.chroma_persist_dir, "persist dir"),
        "artifact_root": _writable_dir_check(settings.artifact_root, "data/runs"),
        "scenarios_zero_locator": _scenarios_zero_locator_check(),
    }
    return {"status": _overall_status(checks), "checks": checks}


def _openai_compatible_check(
    *,
    selected: bool,
    provider_name: str,
    base_url: str,
    model: str,
    configured: bool,
) -> dict[str, str]:
    if configured and base_url and model:
        return _check("ok", f"key configured for {provider_name} / {model}")
    if selected:
        missing = []
        if not base_url:
            missing.append("OPENAI_COMPATIBLE_BASE_URL")
        if not model:
            missing.append("OPENAI_COMPATIBLE_MODEL")
        if not configured:
            missing.append("OPENAI_COMPATIBLE_API_KEY")
        return _check("warning", f"missing {', '.join(missing)}")
    return _check("warning", "not selected")


def _provider_key_check(
    *,
    selected: bool,
    configured: bool,
    configured_detail: str,
    missing_detail: str,
    unselected_detail: str,
) -> dict[str, str]:
    if configured:
        return _check("ok", configured_detail)
    if selected:
        return _check("warning", missing_detail)
    return _check("warning", unselected_detail)


def _key_check(
    configured: bool, configured_detail: str, missing_detail: str
) -> dict[str, str]:
    if configured:
        return _check("ok", configured_detail)
    return _check("warning", missing_detail)


def _package_check(package_name: str) -> dict[str, str]:
    try:
        version = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return _check("error", f"{package_name} not installed")
    return _check("ok", f"{package_name} {version} installed")


def _database_check() -> dict[str, str]:
    try:
        with Session(persistence.engine) as session:
            session.execute(text("select 1")).one()
    except Exception as exc:
        return _check("error", f"sqlite unreachable: {exc}")
    return _check("ok", "sqlite reachable")


def _writable_dir_check(path: Path, label: str) -> dict[str, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".specpilot-doctor"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return _check("error", f"{label} not writable: {exc}")
    return _check("ok", f"{path.as_posix()} writable")


def _scenarios_zero_locator_check() -> dict[str, str]:
    invalid: list[str] = []
    for record in persistence.list_scenario_records():
        try:
            validate_zero_locator_payload(json.loads(record.payload_json))
        except ZeroLocatorValidationError:
            invalid.append(record.scenario_id)

    if invalid:
        return _check("error", f"forbidden locator fields in {', '.join(invalid)}")
    return _check("ok", "persisted scenarios are zero-locator")
