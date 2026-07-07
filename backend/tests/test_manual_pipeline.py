from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from specpilot_backend.config import Settings
from specpilot_backend.ingestion.chunker import ManualChunk
from specpilot_backend.ingestion.crawler import CrawledManualPage
from specpilot_backend.main import app
from specpilot_backend.services import manual_pipeline, persistence


def client_with_settings(monkeypatch) -> Iterator[TestClient]:
    tmp_path = Path(".pytest_cache") / "specpilot-pipeline-tests" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
        openai_compatible_api_key="model-key",
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
        glm_api_key="glm-key",
    )
    monkeypatch.setattr("specpilot_backend.api.pipeline.get_settings", lambda: settings)
    monkeypatch.setattr("specpilot_backend.services.manual_pipeline.get_settings", lambda: settings)
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    with TestClient(app) as test_client:
        yield test_client


def test_job_record_lifecycle_is_persisted(monkeypatch) -> None:
    client = next(client_with_settings(monkeypatch))
    job = persistence.create_job_record(
        job_type="manual_pipeline",
        stage="queued",
        message="等待启动",
    )

    persistence.update_job_record(
        job.job_id,
        status="running",
        stage="crawl",
        progress=25,
        message="正在抓取",
    )
    persistence.update_job_record(
        job.job_id,
        status="failed",
        stage="crawl",
        progress=25,
        error="network timeout",
    )

    response = client.get(f"/api/jobs/{job.job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job.job_id
    assert response.json()["status"] == "failed"
    assert response.json()["stage"] == "crawl"
    assert response.json()["progress"] == 25
    assert response.json()["error"] == "network timeout"


def test_manual_pipeline_replaces_demo_data_only_after_success(monkeypatch) -> None:
    client = next(client_with_settings(monkeypatch))
    demo_feature = {
        "feature_id": "ft_demo",
        "module": "Card",
        "title": "Demo feature",
        "summary": "Demo data",
        "source_urls": ["https://docs.4gaboards.com/docs/user-manual/cards"],
        "evidence_quotes": ["Users can create a card from a list"],
        "confidence": 0.5,
        "coverage_status": "covered",
    }
    demo_scenario = {
        "scenario_id": "sc_demo",
        "feature_id": "ft_demo",
        "title": "Demo scenario",
        "priority": "P1",
        "difficulty": "simple",
        "source_urls": demo_feature["source_urls"],
        "evidence_quotes": demo_feature["evidence_quotes"],
        "preconditions": [],
        "test_data": {},
        "steps": [{"order": 1, "action": "执行 demo"}],
        "expectations": [],
        "max_steps": 10,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
    }
    persistence.save_feature_payload(demo_feature)
    persistence.save_scenario_payload(demo_scenario)

    chunk = ManualChunk(
        content="Users can create a card from a list by clicking Add card.",
        metadata={
            "source_url": "https://docs.4gaboards.com/docs/user-manual/cards#create-card",
            "page_url": "https://docs.4gaboards.com/docs/user-manual/cards",
            "page_title": "Cards",
            "heading_path": "user-manual / Cards / Create card",
            "manual_section": "user-manual",
            "module": "Card",
            "language": "en",
            "is_ui_operational": True,
            "content_hash": "sha256:card",
        },
    )
    page = CrawledManualPage(
        url="https://docs.4gaboards.com/docs/card",
        title="Card",
        markdown="Users can create a card from a list by clicking Add card.",
        manual_section="user-manual",
        module="Card",
        module_variant="card",
    )
    feature = {
        "feature_id": "ft_card_create_card",
        "module": "Card",
        "title": "Create card",
        "summary": "Users can create cards from lists.",
        "source_urls": [chunk.metadata["source_url"]],
        "evidence_quotes": ["Users can create a card from a list"],
        "confidence": 0.91,
        "coverage_status": "covered",
    }
    scenario = {
        "scenario_id": "sc_card_create_card_001",
        "feature_id": feature["feature_id"],
        "title": "在目标 List 中创建新 Card",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": feature["source_urls"],
        "evidence_quotes": feature["evidence_quotes"],
        "preconditions": ["用户已进入一个 Board"],
        "test_data": {"card_title": "SpecPilot Card"},
        "steps": [{"order": 1, "action": "在目标 List 中打开添加 Card 的入口"}],
        "expectations": [
            {
                "type": "element_visible",
                "description": "新建 Card 标题可见",
                "params": {"text": "SpecPilot Card"},
            }
        ],
        "max_steps": 10,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
    }

    monkeypatch.setattr(
        manual_pipeline,
        "crawl_manual_chunks",
        lambda _: manual_pipeline.CrawlOutput(
            crawl_id="crawl_test",
            pages=[page],
            chunks=[chunk],
        ),
    )
    monkeypatch.setattr(manual_pipeline, "index_manual_chunks", lambda _, __: "idx_test")
    monkeypatch.setattr(manual_pipeline, "extract_features_from_chunks", lambda _, __: [feature])
    monkeypatch.setattr(
        manual_pipeline,
        "generate_scenarios_from_features",
        lambda _, __, ___, **____: [scenario],
    )

    response = client.post("/api/pipeline/manual-to-scenarios", json={})
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert job["status"] == "succeeded"
    assert job["result"]["pages"] == [
        {
            "title": "Card",
            "url": "https://docs.4gaboards.com/docs/card",
            "manual_section": "user-manual",
            "module": "Card",
        }
    ]
    assert job["result"]["features"] == [feature]
    assert job["result"]["warnings"] == []
    assert job["result"]["features_count"] == 1
    assert job["result"]["scenarios_count"] == 1
    assert [item["feature_id"] for item in client.get("/api/features").json()["items"]] == [
        feature["feature_id"]
    ]
    assert [
        item["scenario_id"] for item in client.get("/api/scenarios").json()["items"]
    ] == [scenario["scenario_id"]]


def test_manual_pipeline_failure_preserves_existing_data(monkeypatch) -> None:
    client = next(client_with_settings(monkeypatch))
    feature = {
        "feature_id": "ft_existing",
        "module": "Board",
        "title": "Existing",
        "summary": "Keep me",
        "source_urls": ["https://docs.4gaboards.com/docs/user-manual/boards"],
        "evidence_quotes": ["Users can create boards"],
        "confidence": 0.7,
        "coverage_status": "covered",
    }
    persistence.save_feature_payload(feature)

    def fail_crawl(_: object) -> manual_pipeline.CrawlOutput:
        raise RuntimeError("crawl failed")

    monkeypatch.setattr(manual_pipeline, "crawl_manual_chunks", fail_crawl)

    response = client.post("/api/pipeline/manual-to-scenarios", json={})
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()

    assert response.status_code == 200
    assert job["status"] == "failed"
    assert "crawl failed" in job["error"]
    assert client.get("/api/features").json()["items"] == [feature]


def test_manual_pipeline_records_exception_type_when_error_message_is_blank(
    monkeypatch,
) -> None:
    client = next(client_with_settings(monkeypatch))

    def fail_crawl(_: object) -> manual_pipeline.CrawlOutput:
        raise TimeoutError()

    monkeypatch.setattr(manual_pipeline, "crawl_manual_chunks", fail_crawl)

    response = client.post("/api/pipeline/manual-to-scenarios", json={})
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()

    assert job["status"] == "failed"
    assert job["error"] == "TimeoutError"


def test_extract_features_skips_failed_module_when_other_modules_succeed(
    monkeypatch,
) -> None:
    chunks = [
        ManualChunk(
            content="Users can create boards from the dashboard.",
            metadata={
                "source_url": "https://docs.4gaboards.com/docs/board",
                "heading_path": "user-manual / Board",
                "module": "Board",
                "is_ui_operational": True,
            },
        ),
        ManualChunk(
            content="Users can inspect notifications from the notification center.",
            metadata={
                "source_url": "https://docs.4gaboards.com/docs/notifications",
                "heading_path": "user-manual / Notifications",
                "module": "Other",
                "is_ui_operational": True,
            },
        ),
    ]
    calls = 0

    def invoke_model(prompt: str, output_model: object, settings: Settings) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return manual_pipeline._FeatureOutput(
            features=[
                manual_pipeline._FeatureItem(
                    feature_id="ft_notifications_center",
                    module="Notifications",
                    title="Notification Center",
                    summary="Users can inspect notifications.",
                    source_urls=["https://docs.4gaboards.com/docs/notifications"],
                    evidence_quotes=[
                        "Users can inspect notifications from the notification center"
                    ],
                    confidence=0.8,
                    coverage_status="covered",
                )
            ]
        )

    monkeypatch.setattr(manual_pipeline, "_invoke_structured_model", invoke_model)

    features = manual_pipeline.extract_features_from_chunks(
        chunks,
        Settings(_env_file=None, openai_compatible_api_key="model-key"),
    )

    assert [feature["feature_id"] for feature in features] == [
        "ft_notifications_center"
    ]
    assert features[0]["module"] == "Other"


def test_manual_pipeline_resumes_scenario_generation_from_job_features(
    monkeypatch,
) -> None:
    client = next(client_with_settings(monkeypatch))
    feature = {
        "feature_id": "ft_card_create_card",
        "module": "Card",
        "title": "Create card",
        "summary": "Users can create cards from lists.",
        "source_urls": ["https://docs.4gaboards.com/docs/card"],
        "evidence_quotes": ["Users can create a card from a list"],
        "confidence": 0.91,
        "coverage_status": "covered",
    }
    source_job = persistence.create_job_record(
        job_type="manual_pipeline",
        stage="scenarios",
        result={
            "crawl_id": "crawl_source",
            "index_id": "idx_source",
            "pages_count": 1,
            "chunks_count": 1,
            "features_count": 1,
            "features": [feature],
            "warnings": [],
        },
    )
    scenario = {
        "scenario_id": "sc_card_create_card_001",
        "feature_id": feature["feature_id"],
        "title": "在目标 List 中创建新 Card",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": feature["source_urls"],
        "evidence_quotes": feature["evidence_quotes"],
        "preconditions": ["用户已进入一个 Board"],
        "test_data": {"card_title": "SpecPilot Card"},
        "steps": [{"order": 1, "action": "在目标 List 中打开添加 Card 的入口"}],
        "expectations": [
            {
                "type": "element_visible",
                "description": "新建 Card 标题可见",
                "params": {"text": "SpecPilot Card"},
            }
        ],
        "max_steps": 10,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
    }
    monkeypatch.setattr(
        manual_pipeline,
        "generate_scenarios_from_features",
        lambda features, chunks, settings, **kwargs: [scenario],
    )

    response = client.post(
        "/api/pipeline/manual-to-scenarios",
        json={
            "start_stage": "scenarios",
            "resume_from_job_id": source_job.job_id,
            "max_scenarios_per_feature": 2,
        },
    )
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()

    assert response.status_code == 200
    assert job["status"] == "succeeded"
    assert job["result"]["features"] == [feature]
    assert job["result"]["scenarios_count"] == 1
    assert [
        item["scenario_id"] for item in client.get("/api/scenarios").json()["items"]
    ] == [scenario["scenario_id"]]


def test_generate_scenarios_skips_failed_feature_when_other_features_succeed(
    monkeypatch,
) -> None:
    features = [
        {
            "feature_id": "ft_board_create",
            "module": "Board",
            "title": "Create board",
            "summary": "Users can create boards.",
            "source_urls": ["https://docs.4gaboards.com/docs/board"],
            "evidence_quotes": ["Users can create boards"],
            "confidence": 0.8,
            "coverage_status": "covered",
        },
        {
            "feature_id": "ft_card_create",
            "module": "Card",
            "title": "Create card",
            "summary": "Users can create cards.",
            "source_urls": ["https://docs.4gaboards.com/docs/card"],
            "evidence_quotes": ["Users can create cards"],
            "confidence": 0.8,
            "coverage_status": "covered",
        },
    ]
    chunks = [
        ManualChunk(
            content="Users can create boards",
            metadata={"source_url": "https://docs.4gaboards.com/docs/board", "module": "Board"},
        ),
        ManualChunk(
            content="Users can create cards",
            metadata={"source_url": "https://docs.4gaboards.com/docs/card", "module": "Card"},
        ),
    ]
    calls = 0

    def invoke_model(prompt: str, output_model: object, settings: Settings) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return manual_pipeline._ScenarioOutput(
            scenarios=[
                manual_pipeline._ScenarioItem(
                    scenario_id="sc_card_create_001",
                    feature_id="ft_card_create",
                    title="创建 Card",
                    priority="P0",
                    difficulty="simple",
                    source_urls=["https://docs.4gaboards.com/docs/card"],
                    evidence_quotes=["Users can create cards"],
                    preconditions=["用户已进入 Board"],
                    test_data={"card_title": "SpecPilot Card"},
                    steps=[{"order": 1, "action": "创建 Card"}],
                    expectations=[
                        {
                            "type": "element_visible",
                            "description": "Card 可见",
                            "params": {"text": "SpecPilot Card"},
                        }
                    ],
                    max_steps=10,
                    requires_visual_check=False,
                    review_status="auto_validated",
                    is_mutation=False,
                )
            ]
        )

    monkeypatch.setattr(manual_pipeline, "_invoke_structured_model", invoke_model)
    warnings: list[dict[str, object]] = []

    scenarios = manual_pipeline.generate_scenarios_from_features(
        features,
        chunks,
        Settings(_env_file=None, openai_compatible_api_key="model-key"),
        warnings=warnings,
    )

    assert [scenario["scenario_id"] for scenario in scenarios] == ["sc_card_create_001"]
    assert warnings == [
        {
            "stage": "scenarios",
            "scope": "ft_board_create",
            "message": "TimeoutError",
        }
    ]
