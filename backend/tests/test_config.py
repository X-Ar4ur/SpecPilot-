from pathlib import Path

import pytest
from pydantic import ValidationError

from specpilot_backend.config import Settings
from specpilot_backend.db import create_sqlite_engine
from specpilot_backend.ids import new_id


def test_env_example_keys_map_to_settings_fields() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")
    keys = {
        line.split("=", 1)[0]
        for line in env_example.splitlines()
        if line and not line.startswith("#")
    }

    expected_keys = {
        "APP_ENV",
        "BACKEND_HOST",
        "BACKEND_PORT",
        "DATABASE_URL",
        "ARTIFACT_ROOT",
        "CHROMA_PERSIST_DIR",
        "DOCS_BASE_URL",
        "TARGET_APP_URL",
        "FOURGA_USERNAME",
        "FOURGA_PASSWORD",
        "TEXT_LLM_PROVIDER",
        "OPENAI_COMPATIBLE_PROVIDER_NAME",
        "OPENAI_COMPATIBLE_HOME_URL",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_NOTE",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "BROWSER_USE_API_KEY",
        "BROWSER_USE_MODEL",
        "BROWSER_USE_LLM_FALLBACK_ENABLED",
        "BROWSER_USE_CLOUD_BROWSER_ENABLED",
        "GLM_API_KEY",
        "GLM_VISION_MODEL",
        "BROWSER_HEADLESS",
        "BROWSER_ALLOWED_DOMAINS",
        "MAX_SCENARIO_STEPS",
        "RUN_RETRY_LIMIT",
        "VERIFICATION_SNAPSHOT_DELAY_MS",
        "NETWORK_IDLE_TIMEOUT_MS",
        "VISION_CONFIDENCE_HIGH",
        "VISION_CONFIDENCE_LOW",
    }

    assert expected_keys <= keys


def test_default_settings_use_deepseek_v4_pro_and_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_key in (
        "TEXT_LLM_PROVIDER",
        "OPENAI_COMPATIBLE_PROVIDER_NAME",
        "OPENAI_COMPATIBLE_HOME_URL",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_NOTE",
    ):
        monkeypatch.delenv(env_key, raising=False)
    settings = Settings(_env_file=None)

    assert settings.text_llm_provider == "openai_compatible"
    assert settings.openai_compatible_provider_name == "Codex API"
    assert settings.openai_compatible_base_url == "https://api.openai.com/v1"
    assert settings.openai_compatible_model == "gpt-5.5"
    assert settings.deepseek_model == "deepseek-v4-pro"
    assert settings.browser_use_model == "bu-latest"
    assert settings.browser_use_llm_fallback_enabled is False
    assert settings.browser_use_cloud_browser_enabled is False
    assert settings.vision_confidence_high == 0.85
    assert settings.vision_confidence_low == 0.60


def test_dotenv_model_provider_overrides_process_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "TEXT_LLM_PROVIDER=openai_compatible",
                "OPENAI_COMPATIBLE_API_KEY=compatible-key",
                "OPENAI_COMPATIBLE_BASE_URL=https://proxy.example/v1",
                "OPENAI_COMPATIBLE_MODEL=gpt-5.5",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEXT_LLM_PROVIDER", "deepseek")

    settings = Settings(_env_file=env_file)

    assert settings.text_llm_provider == "openai_compatible"


def test_browser_use_api_key_optional_when_not_selected() -> None:
    settings = Settings(
        _env_file=None,
        text_llm_provider="deepseek",
        browser_use_api_key=None,
        browser_use_llm_fallback_enabled=False,
    )

    assert settings.browser_use_api_key is None


def test_openai_compatible_api_key_can_be_empty_until_a_run_uses_it() -> None:
    settings = Settings(
        _env_file=None,
        text_llm_provider="openai_compatible",
        openai_compatible_api_key=None,
    )

    assert settings.openai_compatible_api_key is None


def test_browser_use_api_key_required_when_provider_selected() -> None:
    with pytest.raises(ValidationError, match="BROWSER_USE_API_KEY"):
        Settings(
            _env_file=None,
            text_llm_provider="browser_use",
            browser_use_api_key=None,
            browser_use_llm_fallback_enabled=False,
        )


def test_browser_use_api_key_required_when_fallback_enabled() -> None:
    with pytest.raises(ValidationError, match="BROWSER_USE_API_KEY"):
        Settings(
            _env_file=None,
            text_llm_provider="deepseek",
            browser_use_api_key=None,
            browser_use_llm_fallback_enabled=True,
        )


def test_browser_use_cloud_browser_cannot_be_enabled() -> None:
    with pytest.raises(ValidationError, match="Cloud Browser"):
        Settings(_env_file=None, browser_use_cloud_browser_enabled=True)


def test_database_engine_uses_sqlite_url() -> None:
    settings = Settings(_env_file=None, database_url="sqlite:///./data/specpilot.db")

    engine = create_sqlite_engine(settings)

    assert str(engine.url) == "sqlite:///./data/specpilot.db"


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("ft", "ft_"),
        ("sc", "sc_"),
        ("run", "run_"),
        ("crawl", "crawl_"),
        ("idx", "idx_"),
        ("job", "job_"),
    ],
)
def test_id_helpers_use_required_prefixes(prefix: str, expected: str) -> None:
    generated = new_id(prefix)

    assert generated.startswith(expected)
