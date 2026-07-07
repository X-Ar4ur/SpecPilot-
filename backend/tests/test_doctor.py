from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from specpilot_backend.config import Settings
from specpilot_backend.main import app
from specpilot_backend.services import persistence


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    tmp_path = Path(".pytest_cache") / "specpilot-doctor-tests" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        text_llm_provider="deepseek",
        openai_compatible_api_key=None,
        deepseek_api_key="deepseek-test-key",
        browser_use_api_key=None,
        glm_api_key="glm-test-key",
    )
    monkeypatch.setattr("specpilot_backend.api.doctor.get_settings", lambda: settings)
    monkeypatch.setattr("specpilot_backend.api.runs.get_settings", lambda: settings)
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    with TestClient(app) as test_client:
        yield test_client


def test_doctor_reports_required_local_readiness_checks(
    client: TestClient,
) -> None:
    response = client.get("/api/doctor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "warning"}
    assert set(payload["checks"]) >= {
        "text_llm_provider",
        "deepseek_api",
        "browser_use_llm",
        "browser_use_cloud_browser",
        "glm_vision_api",
        "browser_use",
        "database",
        "chroma",
        "artifact_root",
        "scenarios_zero_locator",
    }
    assert payload["checks"]["text_llm_provider"]["detail"] == "deepseek"
    assert payload["checks"]["deepseek_api"]["status"] == "ok"
    assert "openai_compatible_api" in payload["checks"]
    assert payload["checks"]["browser_use_llm"]["status"] == "warning"
    assert payload["checks"]["browser_use_cloud_browser"] == {
        "status": "ok",
        "detail": "disabled for MVP",
    }
    assert payload["checks"]["glm_vision_api"]["status"] == "ok"


def test_doctor_checks_openai_compatible_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        text_llm_provider="openai_compatible",
        openai_compatible_provider_name="Clauddy",
        openai_compatible_base_url="https://clauddy.com/v1",
        openai_compatible_model="gpt-5.5",
        openai_compatible_api_key="openai-compatible-key",
        glm_api_key="glm-test-key",
    )
    monkeypatch.setattr("specpilot_backend.api.doctor.get_settings", lambda: settings)

    response = client.get("/api/doctor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["text_llm_provider"]["detail"] == "openai_compatible"
    assert payload["checks"]["openai_compatible_api"] == {
        "status": "ok",
        "detail": "key configured for Clauddy / gpt-5.5",
    }


def test_doctor_flags_invalid_persisted_locator_scenario(
    client: TestClient,
) -> None:
    persistence.save_scenario_payload(
        {
            "scenario_id": "sc_bad_locator",
            "feature_id": "ft_bad",
            "title": "含定位字段的错误场景",
            "priority": "P1",
            "difficulty": "simple",
            "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
            "evidence_quotes": ["Cards can be created from a list."],
            "preconditions": ["用户已进入 Board"],
            "test_data": {"selector": "#bad"},
            "steps": [{"order": 1, "action": "创建 Card"}],
            "expectations": [
                {
                    "type": "text_present",
                    "description": "页面出现 Card 标题",
                    "params": {"text": "SpecPilot Card"},
                }
            ],
            "max_steps": 10,
            "requires_visual_check": False,
            "review_status": "auto_validated",
            "is_mutation": False,
        }
    )

    response = client.get("/api/doctor")

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["checks"]["scenarios_zero_locator"]["status"] == "error"
