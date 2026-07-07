from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    database_url: str = "sqlite:///./data/specpilot.db"
    artifact_root: Path = Path("./data/runs")
    chroma_persist_dir: Path = Path("./data/chroma")

    docs_base_url: str = "https://docs.4gaboards.com/"
    target_app_url: str = "https://demo.4gaboards.com/"
    fourga_username: str | None = None
    fourga_password: SecretStr | None = None
    # 4ga REST API base used by FourgaApiClient for fixture inventory/creation.
    # Falls back to target_app_url when unset; point it at the backend port
    # (e.g. http://localhost:1337), not the frontend dev-server proxy.
    fourga_api_base_url: str | None = None

    text_llm_provider: Literal[
        "openai_compatible", "deepseek", "browser_use"
    ] = "openai_compatible"
    openai_compatible_provider_name: str = "Codex API"
    openai_compatible_home_url: str = "https://openai.com"
    openai_compatible_base_url: str = "https://api.openai.com/v1"
    openai_compatible_api_key: SecretStr | None = None
    openai_compatible_model: str = "gpt-5.5"
    openai_compatible_note: str | None = None
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-v4-pro"
    browser_use_api_key: SecretStr | None = None
    browser_use_model: str = "bu-latest"
    browser_use_llm_fallback_enabled: bool = False
    browser_use_cloud_browser_enabled: bool = False
    glm_api_key: SecretStr | None = None
    glm_vision_model: str = "glm-4.6v"

    browser_headless: bool = True
    browser_allowed_domains: str = "*.4gaboards.com"
    max_scenario_steps: int = Field(default=20, ge=1)
    run_retry_limit: int = Field(default=1, ge=0)
    verification_snapshot_delay_ms: int = Field(default=500, ge=0)
    network_idle_timeout_ms: int = Field(default=3000, ge=0)
    vision_confidence_high: float = Field(default=0.85, ge=0.0, le=1.0)
    vision_confidence_low: float = Field(default=0.60, ge=0.0, le=1.0)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, Any, Any, Any]:
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    @field_validator(
        "fourga_username",
        "fourga_password",
        "fourga_api_base_url",
        "openai_compatible_api_key",
        "deepseek_api_key",
        "browser_use_api_key",
        "glm_api_key",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def validate_model_provider_settings(self) -> "Settings":
        if self.browser_use_cloud_browser_enabled:
            msg = "Browser Use Cloud Browser is disabled for the MVP"
            raise ValueError(msg)
        if (
            self.text_llm_provider == "browser_use"
            or self.browser_use_llm_fallback_enabled
        ) and self.browser_use_api_key is None:
            msg = "BROWSER_USE_API_KEY is required for Browser Use hosted LLM"
            raise ValueError(msg)
        if self.vision_confidence_low > self.vision_confidence_high:
            msg = "VISION_CONFIDENCE_LOW must not exceed VISION_CONFIDENCE_HIGH"
            raise ValueError(msg)
        return self


def get_settings() -> Settings:
    return Settings()
