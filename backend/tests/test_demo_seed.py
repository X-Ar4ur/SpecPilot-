from pathlib import Path
from uuid import uuid4

from specpilot_backend.config import Settings
from specpilot_backend.demo import DEMO_FEATURES, DEMO_SCENARIOS, seed_demo_data
from specpilot_backend.generation.validators import validate_zero_locator_payload
from specpilot_backend.services import persistence


def test_demo_seed_contains_required_e2e_scenarios_and_no_locators() -> None:
    titles = {str(scenario["title"]) for scenario in DEMO_SCENARIOS}

    assert len(DEMO_FEATURES) >= 6
    assert len(DEMO_SCENARIOS) >= 6
    assert {
        "创建 Board 并验证名称可见",
        "创建 List 并验证列表可见",
        "创建 Card 并验证目标 List 中出现",
        "编辑 Card 标题和描述并验证更新",
        "拖拽 Card 到另一 List 并验证归属",
        "切换 Board/List 视图并验证视觉状态",
    } <= titles
    for scenario in DEMO_SCENARIOS:
        validate_zero_locator_payload(scenario)


def test_seed_demo_data_persists_features_and_scenarios() -> None:
    tmp_path = Path(".pytest_cache") / "specpilot-demo-tests" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()

    summary = seed_demo_data()

    assert summary == {"features": len(DEMO_FEATURES), "scenarios": len(DEMO_SCENARIOS)}
    assert len(persistence.list_feature_payloads()) == len(DEMO_FEATURES)
    assert len(persistence.list_scenario_records(is_mutation=False)) == len(
        DEMO_SCENARIOS
    )
