from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

FEATURE_EXTRACTION_PROMPT = """You extract user-visible 4ga Boards feature points from manual evidence.

Return only JSON with this shape:
{
  "features": [
    {
      "feature_id": "ft_card_creation",
      "module": "Card",
      "title": "创建 Card",
      "summary": "用户可以在指定 List 中创建 Card。",
      "source_urls": ["https://docs.4gaboards.com/cards/create"],
      "evidence_quotes": ["..."],
      "confidence": 0.91
    }
  ]
}

Rules:
- Do not invent features not supported by quotes.
- Every feature must cite source_urls and evidence_quotes from the supplied chunks.
- Every evidence quote must be copied from a supplied chunk.
- Use stable snake_case ids beginning with ft_.
- Keep feature granularity at user-visible capability level, not individual button level.
- Do not include secrets, credentials, API keys, or test passwords.
"""

SCENARIO_GENERATION_PROMPT = """You generate executable zero-locator test scenarios from one feature and manual evidence.

Return only JSON with this shape:
{
  "scenarios": [
    {
      "scenario_id": "sc_create_card_001",
      "feature_id": "ft_card_creation",
      "title": "在指定 List 中创建新 Card",
      "priority": "P0",
      "difficulty": "simple",
      "source_urls": ["https://docs.4gaboards.com/cards/create"],
      "evidence_quotes": ["..."],
      "preconditions": ["用户已进入一个 Board"],
      "test_data": {"card_title": "完成季度报告"},
      "steps": [{"order": 1, "action": "在目标 List 中打开添加 Card 的入口"}],
      "expectations": [
        {
          "type": "element_visible",
          "description": "新建 Card 标题在目标 List 中可见",
          "params": {"text": "完成季度报告", "container_text": "To Do"}
        }
      ],
      "max_steps": 20,
      "requires_visual_check": false,
      "review_status": "auto_validated",
      "data_dependency": "self_seeding",
      "fixtures": []
    },
    {
      "scenario_id": "sc_open_card_001",
      "feature_id": "ft_card_open",
      "title": "从 List View 打开对应 Card",
      "priority": "P0",
      "difficulty": "simple",
      "source_urls": ["https://docs.4gaboards.com/cards/open"],
      "evidence_quotes": ["..."],
      "preconditions": ["List View 中存在一张可识别标题的 Card"],
      "test_data": {"card_title": "{{fixture.target_card.title}}"},
      "steps": [{"order": 1, "action": "在 List View 中打开标题为 {{fixture.target_card.title}} 的 Card"}],
      "expectations": [
        {
          "type": "element_visible",
          "description": "对应 Card 的详情视图被打开并显示标题",
          "params": {"text": "{{fixture.target_card.title}}"}
        }
      ],
      "max_steps": 6,
      "requires_visual_check": false,
      "review_status": "auto_validated",
      "data_dependency": "interactive",
      "fixtures": [
        {"ref": "target_card", "kind": "card", "required_attrs": ["title"], "allow_create": true}
      ]
    }
  ]
}

Rules:
- Never output selector, locator, xpath, element_id, element_index, css, or css_selector fields.
- Step actions must be natural-language user intentions, not DOM targeting instructions.
- Every scenario must include evidence quotes from the supplied chunks.
- Every evidence quote must be copied from supplied evidence.
- Prefer 2-6 user action steps; steps must never be empty.
- max_steps must be a positive integer (20 for simple, 20 for medium, 35 for hard).
- Allowed expectation types are exactly: element_visible, text_present, url_match, element_state, containment, semantic. Never invent other types such as element_not_visible.
- To assert that something is absent, removed, or hidden, use {"type": "text_present", "params": {"text": "...", "not_present": true}}.
- Use semantic expectation only when DOM/text/URL checks are insufficient.
- Classify data_dependency: "self_seeding" when the scenario creates the data it then checks (create/edit); "interactive" when it depends on a pre-existing element (open/view/search/filter/move/delete); "none" when no specific element is required.
- For "self_seeding" and "none" scenarios set "fixtures": [] and never use fixture tokens.
- For "interactive" scenarios declare each required element in "fixtures" (ref, kind, optional parent_ref, required_attrs, allow_create) and reference its value with {{fixture.<ref>.<attr>}} tokens in test_data, steps, and expectations. Never hardcode a concrete element value that may be absent from the target instance.
- Fixture tokens may only use these attributes: card -> title, list_name, board_name, project_name; list -> name, board_name, project_name; board -> name, project_name; project -> name. Do not invent other attribute names.
- Mark unsupported or weak-evidence scenarios as rejected.
- Do not include secrets, credentials, API keys, or test passwords.
"""


def build_feature_extraction_prompt(
    evidence_chunks: Iterable[Mapping[str, Any]],
) -> str:
    return "\n\n".join(
        (
            FEATURE_EXTRACTION_PROMPT,
            "Evidence chunks:",
            json.dumps(list(evidence_chunks), ensure_ascii=False, indent=2),
        )
    )


def build_scenario_generation_prompt(
    *,
    feature: Mapping[str, Any],
    evidence_chunks: Iterable[Mapping[str, Any]],
) -> str:
    return "\n\n".join(
        (
            SCENARIO_GENERATION_PROMPT,
            "Feature:",
            json.dumps(feature, ensure_ascii=False, indent=2),
            "Evidence chunks:",
            json.dumps(list(evidence_chunks), ensure_ascii=False, indent=2),
        )
    )
