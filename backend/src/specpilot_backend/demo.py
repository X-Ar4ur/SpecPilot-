from __future__ import annotations

from typing import Final

from specpilot_backend.generation.validators import validate_zero_locator_payload
from specpilot_backend.services.persistence import (
    save_feature_payload,
    save_scenario_payload,
)

DEMO_FEATURES: Final[list[dict[str, object]]] = [
    {
        "feature_id": "ft_demo_create_board",
        "module": "Board",
        "title": "Create board",
        "summary": "Users can create a board and verify the board name.",
        "source_urls": ["https://docs.4gaboards.com/user-manual/boards"],
        "evidence_quotes": ["Create a board to organize lists and cards."],
        "confidence": 0.82,
        "coverage_status": "covered",
    },
    {
        "feature_id": "ft_demo_create_list",
        "module": "List",
        "title": "Create list",
        "summary": "Users can add a list to an existing board.",
        "source_urls": ["https://docs.4gaboards.com/user-manual/lists"],
        "evidence_quotes": ["Lists group cards on a board."],
        "confidence": 0.82,
        "coverage_status": "covered",
    },
    {
        "feature_id": "ft_demo_create_card",
        "module": "Card",
        "title": "Create card",
        "summary": "Users can create a card inside a target list.",
        "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
        "evidence_quotes": ["Cards represent work items in lists."],
        "confidence": 0.84,
        "coverage_status": "covered",
    },
    {
        "feature_id": "ft_demo_edit_card",
        "module": "Card",
        "title": "Edit card",
        "summary": "Users can edit card title and description.",
        "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
        "evidence_quotes": ["Open a card to edit its details."],
        "confidence": 0.82,
        "coverage_status": "covered",
    },
    {
        "feature_id": "ft_demo_move_card",
        "module": "Card",
        "title": "Move card",
        "summary": "Users can move a card from one list to another.",
        "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
        "evidence_quotes": ["Move cards between lists as work progresses."],
        "confidence": 0.80,
        "coverage_status": "covered",
    },
    {
        "feature_id": "ft_demo_switch_view",
        "module": "Views",
        "title": "Switch view",
        "summary": "Users can switch board or list views and verify visual state.",
        "source_urls": ["https://docs.4gaboards.com/user-manual/views"],
        "evidence_quotes": ["Views help inspect board information in different layouts."],
        "confidence": 0.78,
        "coverage_status": "covered",
    },
]

DEMO_SCENARIOS: Final[list[dict[str, object]]] = [
    {
        "scenario_id": "sc_demo_create_board",
        "feature_id": "ft_demo_create_board",
        "title": "创建 Board 并验证名称可见",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/user-manual/boards"],
        "evidence_quotes": ["Create a board to organize lists and cards."],
        "preconditions": ["用户已登录 4ga Boards demo 环境"],
        "test_data": {"board_name": "SpecPilot Acceptance Board"},
        "steps": [
            {"order": 1, "action": "打开创建 Board 的入口"},
            {"order": 2, "action": "输入 Board 名称并确认创建"},
            {"order": 3, "action": "进入新创建的 Board"},
        ],
        "expectations": [
            {
                "type": "text_present",
                "description": "页面可见新创建的 Board 名称",
                "params": {"text": "SpecPilot Acceptance Board"},
            }
        ],
        "max_steps": 20,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
    },
    {
        "scenario_id": "sc_demo_create_list",
        "feature_id": "ft_demo_create_list",
        "title": "创建 List 并验证列表可见",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/user-manual/lists"],
        "evidence_quotes": ["Lists group cards on a board."],
        "preconditions": ["用户已进入 SpecPilot Acceptance Board"],
        "test_data": {"list_name": "SpecPilot To Do"},
        "steps": [
            {"order": 1, "action": "在当前 Board 中打开添加 List 的入口"},
            {"order": 2, "action": "输入 List 名称并确认创建"},
        ],
        "expectations": [
            {
                "type": "element_visible",
                "description": "新创建的 List 在 Board 中可见",
                "params": {"text": "SpecPilot To Do"},
            }
        ],
        "max_steps": 20,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
    },
    {
        "scenario_id": "sc_demo_create_card",
        "feature_id": "ft_demo_create_card",
        "title": "创建 Card 并验证目标 List 中出现",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
        "evidence_quotes": ["Cards represent work items in lists."],
        "preconditions": ["Board 中存在名为 SpecPilot To Do 的 List"],
        "test_data": {
            "card_title": "SpecPilot Quarterly Report",
            "target_list_name": "SpecPilot To Do",
        },
        "steps": [
            {"order": 1, "action": "在目标 List 中打开添加 Card 的入口"},
            {"order": 2, "action": "输入 Card 标题并确认创建"},
        ],
        "expectations": [
            {
                "type": "containment",
                "description": "新 Card 位于目标 List 内",
                "params": {
                    "child_text": "SpecPilot Quarterly Report",
                    "parent_label": "SpecPilot To Do",
                },
            }
        ],
        "max_steps": 20,
        "requires_visual_check": False,
        "review_status": "auto_validated",
        "is_mutation": False,
    },
    {
        "scenario_id": "sc_demo_edit_card",
        "feature_id": "ft_demo_edit_card",
        "title": "编辑 Card 标题和描述并验证更新",
        "priority": "P1",
        "difficulty": "medium",
        "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
        "evidence_quotes": ["Open a card to edit its details."],
        "preconditions": ["目标 List 中存在 SpecPilot Quarterly Report Card"],
        "test_data": {
            "original_card_title": "SpecPilot Quarterly Report",
            "updated_card_title": "SpecPilot Final Report",
            "updated_description": "Prepared during SpecPilot acceptance.",
        },
        "steps": [
            {"order": 1, "action": "打开目标 Card 的详情"},
            {"order": 2, "action": "将 Card 标题更新为测试标题"},
            {"order": 3, "action": "填写测试描述并保存"},
            {"order": 4, "action": "返回 Board 视图"},
        ],
        "expectations": [
            {
                "type": "text_present",
                "description": "更新后的 Card 标题在页面中可见",
                "params": {"text": "SpecPilot Final Report"},
            },
            {
                "type": "semantic",
                "description": "Card 详情保存了新的描述内容",
                "params": {"expected_summary": "description was updated"},
            },
        ],
        "max_steps": 16,
        "requires_visual_check": True,
        "review_status": "auto_validated",
        "is_mutation": False,
    },
    {
        "scenario_id": "sc_demo_drag_card",
        "feature_id": "ft_demo_move_card",
        "title": "拖拽 Card 到另一 List 并验证归属",
        "priority": "P1",
        "difficulty": "medium",
        "source_urls": ["https://docs.4gaboards.com/user-manual/cards"],
        "evidence_quotes": ["Move cards between lists as work progresses."],
        "preconditions": [
            "Board 中存在 SpecPilot To Do 与 SpecPilot Done 两个 List",
            "SpecPilot To Do 中存在 SpecPilot Final Report Card",
        ],
        "test_data": {
            "card_title": "SpecPilot Final Report",
            "source_list_name": "SpecPilot To Do",
            "target_list_name": "SpecPilot Done",
        },
        "steps": [
            {"order": 1, "action": "找到目标 Card"},
            {"order": 2, "action": "将目标 Card 移动到目标 List"},
            {"order": 3, "action": "确认目标 List 中显示该 Card"},
        ],
        "expectations": [
            {
                "type": "containment",
                "description": "目标 Card 位于目标 List 内",
                "params": {
                    "child_text": "SpecPilot Final Report",
                    "parent_label": "SpecPilot Done",
                },
            }
        ],
        "max_steps": 18,
        "requires_visual_check": True,
        "review_status": "auto_validated",
        "is_mutation": False,
    },
    {
        "scenario_id": "sc_demo_switch_view",
        "feature_id": "ft_demo_switch_view",
        "title": "切换 Board/List 视图并验证视觉状态",
        "priority": "P1",
        "difficulty": "medium",
        "source_urls": ["https://docs.4gaboards.com/user-manual/views"],
        "evidence_quotes": ["Views help inspect board information in different layouts."],
        "preconditions": ["用户已进入包含多个 List 与 Card 的 Board"],
        "test_data": {"expected_board_name": "SpecPilot Acceptance Board"},
        "steps": [
            {"order": 1, "action": "打开 Board 或 List 视图切换入口"},
            {"order": 2, "action": "切换到另一种可用视图"},
            {"order": 3, "action": "观察当前 Board 信息仍然可见"},
        ],
        "expectations": [
            {
                "type": "semantic",
                "description": "页面视觉状态呈现为已切换后的视图，且 Board 内容仍可识别",
                "params": {"expected_board_name": "SpecPilot Acceptance Board"},
            }
        ],
        "max_steps": 18,
        "requires_visual_check": True,
        "review_status": "auto_validated",
        "is_mutation": False,
    },
]


def seed_demo_data() -> dict[str, int]:
    for feature in DEMO_FEATURES:
        save_feature_payload(feature)
    for scenario in DEMO_SCENARIOS:
        validate_zero_locator_payload(scenario)
        save_scenario_payload(scenario)
    return {"features": len(DEMO_FEATURES), "scenarios": len(DEMO_SCENARIOS)}
