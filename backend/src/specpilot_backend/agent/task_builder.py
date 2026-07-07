from __future__ import annotations

import json
from typing import Any

from specpilot_backend.models.scenarios import TestScenario

SENSITIVE_TEST_DATA_KEYS = {
    "api_key",
    "auth_token",
    "credential",
    "password",
    "secret",
    "token",
    "username",
}


def build_browser_use_task(
    scenario: TestScenario,
    *,
    target_app_url: str,
    include_login_guidance: bool = False,
) -> str:
    _reject_sensitive_step_text(scenario)
    non_sensitive_test_data = _non_sensitive_test_data(scenario.test_data)
    preconditions = "\n".join(f"- {item}" for item in scenario.preconditions) or "- 无"
    test_data = json.dumps(
        non_sensitive_test_data,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    ordered_steps = "\n".join(
        f"{step.order}. {step.action}"
        for step in sorted(scenario.steps, key=lambda item: item.order)
    )
    rules = [
        "- Stay within the configured target application.",
        "- Use the UI like a human user.",
    ]
    if include_login_guidance:
        rules.extend(
            [
                "- If a login screen appears, sign in with secure placeholders: "
                "use <secret>FOURGA_USERNAME</secret> for the username/email "
                "field and <secret>FOURGA_PASSWORD</secret> for the password field.",
                "- Never type or reveal the real credential values; only use "
                "the secret placeholders above.",
            ]
        )
    rules.extend(
        [
            "- Do not use selectors or developer tools.",
            "- Do not expose credentials in logs.",
            "- Stop when the requested task steps are complete.",
        ]
    )
    rendered_rules = "\n".join(rules)
    return f"""You are testing 4ga Boards at {target_app_url}. Complete this scenario using the UI like a human user.

Scenario: {scenario.title}

Preconditions:
{preconditions}

Test data:
{test_data}

Task steps:
{ordered_steps}

Rules:
{rendered_rules}
"""


def _non_sensitive_test_data(test_data: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in test_data.items()
        if key.lower() not in SENSITIVE_TEST_DATA_KEYS
    }


def _reject_sensitive_step_text(scenario: TestScenario) -> None:
    for step in scenario.steps:
        lowered = step.action.lower()
        if any(key in lowered for key in SENSITIVE_TEST_DATA_KEYS):
            msg = "Scenario step text appears to reference sensitive data."
            raise ValueError(msg)


def contains_sensitive_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in SENSITIVE_TEST_DATA_KEYS
            or contains_sensitive_value(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(contains_sensitive_value(item) for item in value)
    return False
