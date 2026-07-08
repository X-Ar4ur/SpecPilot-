from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from specpilot_backend.generation.validators import validate_scenario_payload
from specpilot_backend.ingestion.chunker import ManualChunk


def generate_scenario_payloads(
    features: list[dict[str, object]],
    evidence_by_feature_id: Mapping[str, list[ManualChunk]],
    *,
    persist: bool = False,
) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for feature in features:
        feature_id = str(feature["feature_id"])
        evidence_chunks = evidence_by_feature_id.get(feature_id, [])
        if not evidence_chunks:
            continue
        scenario = _scenario_for_feature(feature)
        validate_scenario_payload(scenario, evidence_chunks)
        scenarios.append(scenario)

    if persist:
        from specpilot_backend.services.persistence import save_scenario_payload

        for scenario in scenarios:
            save_scenario_payload(scenario)
    return scenarios


def _scenario_for_feature(feature: dict[str, object]) -> dict[str, Any]:
    module = str(feature["module"])
    title = str(feature["title"])
    scenario_id = f"sc_{module.lower()}_{_scenario_slug(title)}_001"
    test_title = "自动化验证：" + title
    test_value = f"SpecPilot {title}"

    if module == "Card" and "create" in title.lower():
        test_title = "在目标 List 中创建新 Card"
        test_value = "SpecPilot Card"
        steps = [
            {"order": 1, "action": "打开包含目标 List 的 Board"},
            {"order": 2, "action": "在目标 List 中打开添加 Card 的入口"},
            {"order": 3, "action": "输入测试 Card 标题并确认创建"},
        ]
        expectations = [
            {
                "type": "element_visible",
                "description": "新建 Card 标题在目标 List 中可见",
                "params": {"text": test_value, "container_text": "目标 List"},
            }
        ]
        test_data = {"card_title": test_value, "target_list_name": "目标 List"}
        preconditions = ["用户已进入一个包含目标 List 的 Board"]
    else:
        steps = [
            {"order": 1, "action": f"打开 {module} 相关页面"},
            {"order": 2, "action": f"按照手册说明执行 {title}"},
        ]
        expectations = [
            {
                "type": "text_present",
                "description": f"页面展示与 {title} 相关的结果或状态",
                "params": {"text": test_value},
            }
        ]
        test_data = {"expected_text": test_value}
        preconditions = [f"用户已登录并具备访问 {module} 模块的权限"]

    return {
        "scenario_id": scenario_id,
        "feature_id": feature["feature_id"],
        "title": test_title,
        "priority": _priority_for(module),
        "difficulty": _difficulty_for(module),
        "source_urls": feature["source_urls"],
        "evidence_quotes": feature["evidence_quotes"],
        "preconditions": preconditions,
        "test_data": test_data,
        "steps": steps,
        "expectations": expectations,
        "max_steps": _max_steps_for(module),
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
        "data_dependency": (
            "self_seeding"
            if module == "Card" and "create" in title.lower()
            else "none"
        ),
        "fixtures": [],
    }


def _scenario_slug(title: str) -> str:
    return "_".join(part for part in title.lower().split() if part)


def _priority_for(module: str) -> str:
    return "P0" if module in {"Project", "Board"} else "P1"


def _difficulty_for(module: str) -> str:
    return "medium" if module in {"Views", "Admin", "Settings"} else "simple"


def _max_steps_for(module: str) -> int:
    return 20 if _difficulty_for(module) in {"simple", "medium"} else 35
