from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from specpilot_backend.config import Settings, get_settings
from specpilot_backend.services.env_file import write_env_values

router = APIRouter(prefix="/api/settings", tags=["settings"])
ENV_FILE_PATH = Path(".env")


class ModelSettingsPatch(BaseModel):
    text_llm_provider: Literal["openai_compatible", "deepseek", "browser_use"] | None = None
    openai_compatible_provider_name: str | None = None
    openai_compatible_home_url: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None
    openai_compatible_note: str | None = None
    deepseek_model: str | None = None
    deepseek_api_key: str | None = None
    browser_use_model: str | None = None
    browser_use_api_key: str | None = None
    browser_use_llm_fallback_enabled: bool | None = None
    browser_use_cloud_browser_enabled: bool | None = None
    glm_vision_model: str | None = None
    glm_api_key: str | None = None


class SettingsPatch(BaseModel):
    models: ModelSettingsPatch


def _secret_configured(secret: object) -> bool:
    return secret is not None


def settings_response(settings: Settings) -> dict[str, object]:
    return {
        "models": {
            "text_llm_provider": settings.text_llm_provider,
            "openai_compatible_provider_name": (
                settings.openai_compatible_provider_name
            ),
            "openai_compatible_home_url": settings.openai_compatible_home_url,
            "openai_compatible_base_url": settings.openai_compatible_base_url,
            "openai_compatible_model": settings.openai_compatible_model,
            "openai_compatible_note": settings.openai_compatible_note,
            "openai_compatible_api_key_configured": _secret_configured(
                settings.openai_compatible_api_key
            ),
            "deepseek_model": settings.deepseek_model,
            "deepseek_api_key_configured": _secret_configured(
                settings.deepseek_api_key
            ),
            "browser_use_model": settings.browser_use_model,
            "browser_use_api_key_configured": _secret_configured(
                settings.browser_use_api_key
            ),
            "browser_use_llm_fallback_enabled": (
                settings.browser_use_llm_fallback_enabled
            ),
            "browser_use_cloud_browser_enabled": False,
            "glm_vision_model": settings.glm_vision_model,
            "glm_api_key_configured": _secret_configured(settings.glm_api_key),
        }
    }


@router.get("")
def get_runtime_settings() -> dict[str, object]:
    return settings_response(get_settings())


@router.patch("")
def patch_runtime_settings(patch: SettingsPatch) -> dict[str, object]:
    if patch.models.browser_use_cloud_browser_enabled:
        raise HTTPException(
            status_code=422,
            detail="Browser Use Cloud Browser is disabled for the MVP",
        )
    current = get_settings()
    updates = _env_updates(patch.models)
    if updates:
        write_env_values(ENV_FILE_PATH, updates)
    response = settings_response(current.model_copy(update=_runtime_updates(patch.models)))
    models = response["models"]
    if isinstance(models, dict):
        _set_secret_configured_flags(models, patch.models)
    return response


def _env_updates(models: ModelSettingsPatch) -> dict[str, str]:
    updates: dict[str, str] = {}
    mapping = {
        "text_llm_provider": "TEXT_LLM_PROVIDER",
        "openai_compatible_provider_name": "OPENAI_COMPATIBLE_PROVIDER_NAME",
        "openai_compatible_home_url": "OPENAI_COMPATIBLE_HOME_URL",
        "openai_compatible_base_url": "OPENAI_COMPATIBLE_BASE_URL",
        "openai_compatible_model": "OPENAI_COMPATIBLE_MODEL",
        "openai_compatible_note": "OPENAI_COMPATIBLE_NOTE",
        "deepseek_model": "DEEPSEEK_MODEL",
        "browser_use_model": "BROWSER_USE_MODEL",
        "glm_vision_model": "GLM_VISION_MODEL",
    }
    payload = models.model_dump()
    for field, env_key in mapping.items():
        value = payload.get(field)
        if value is not None:
            updates[env_key] = str(value)

    bool_mapping = {
        "browser_use_llm_fallback_enabled": "BROWSER_USE_LLM_FALLBACK_ENABLED",
        "browser_use_cloud_browser_enabled": "BROWSER_USE_CLOUD_BROWSER_ENABLED",
    }
    for field, env_key in bool_mapping.items():
        value = payload.get(field)
        if value is not None:
            updates[env_key] = str(value).lower()

    secret_mapping = {
        "openai_compatible_api_key": "OPENAI_COMPATIBLE_API_KEY",
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "browser_use_api_key": "BROWSER_USE_API_KEY",
        "glm_api_key": "GLM_API_KEY",
    }
    for field, env_key in secret_mapping.items():
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            updates[env_key] = value
    return updates


def _runtime_updates(models: ModelSettingsPatch) -> dict[str, object]:
    return {
        key: value
        for key, value in models.model_dump().items()
        if value is not None and not key.endswith("_api_key")
    }


def _set_secret_configured_flags(
    models: dict[str, object],
    patch: ModelSettingsPatch,
) -> None:
    secret_flags = {
        "openai_compatible_api_key": (
            "OPENAI_COMPATIBLE_API_KEY",
            "openai_compatible_api_key_configured",
        ),
        "deepseek_api_key": ("DEEPSEEK_API_KEY", "deepseek_api_key_configured"),
        "browser_use_api_key": (
            "BROWSER_USE_API_KEY",
            "browser_use_api_key_configured",
        ),
        "glm_api_key": ("GLM_API_KEY", "glm_api_key_configured"),
    }
    payload = patch.model_dump()
    submitted = patch.model_fields_set
    existing = _read_env_values(ENV_FILE_PATH)
    for field, (env_key, flag) in secret_flags.items():
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            models[flag] = True
        elif field in submitted:
            models[flag] = bool(existing.get(env_key))


def _read_env_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values
