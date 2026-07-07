import pytest

from specpilot_backend.agent.browser_use_runner import (
    build_initial_actions,
    build_sensitive_data,
    create_browser_session,
    effective_max_steps,
)
from specpilot_backend.agent.task_builder import build_browser_use_task
from specpilot_backend.config import Settings
from specpilot_backend.models.scenarios import TestScenario


def scenario_payload() -> dict[str, object]:
    return {
        "scenario_id": "sc_create_card_001",
        "feature_id": "ft_card_creation",
        "title": "在指定 List 中创建新 Card",
        "priority": "P0",
        "difficulty": "simple",
        "source_urls": ["https://docs.4gaboards.com/cards/create"],
        "evidence_quotes": ["Click Add Card to create a new card."],
        "preconditions": ["用户已进入一个 Board"],
        "test_data": {
            "card_title": "完成季度报告",
            "target_list_name": "To Do",
            "password": "should-not-enter-task",
            "api_key": "should-not-enter-task",
        },
        "steps": [
            {"order": 1, "action": "在目标 List 中打开添加 Card 的入口"},
            {"order": 2, "action": "输入 Card 标题"},
        ],
        "expectations": [
            {
                "type": "element_visible",
                "description": "新建 Card 标题在目标 List 中可见",
                "params": {"text": "完成季度报告"},
            }
        ],
        "max_steps": 10,
        "requires_visual_check": False,
        "review_status": "auto_validated",
    }


def test_task_builder_uses_steps_preconditions_and_non_sensitive_test_data_only() -> None:
    scenario = TestScenario.model_validate(scenario_payload())
    task = build_browser_use_task(
        scenario,
        target_app_url="https://demo.4gaboards.com/",
    )

    assert "You are testing 4ga Boards at https://demo.4gaboards.com/" in task
    assert "用户已进入一个 Board" in task
    assert "完成季度报告" in task
    assert "To Do" in task
    assert "在目标 List 中打开添加 Card 的入口" in task
    assert "新建 Card 标题在目标 List 中可见" not in task
    assert "expectations" not in task.lower()
    assert "should-not-enter-task" not in task
    assert "api_key" not in task.lower()


def test_task_builder_uses_secret_placeholders_for_login_guidance() -> None:
    scenario = TestScenario.model_validate(scenario_payload())
    task = build_browser_use_task(
        scenario,
        target_app_url="http://localhost:3000/",
        include_login_guidance=True,
    )

    assert "<secret>FOURGA_USERNAME</secret>" in task
    assert "<secret>FOURGA_PASSWORD</secret>" in task
    assert "alice@example.com" not in task
    assert "secret-password" not in task


def test_task_builder_does_not_add_a_second_url_for_scope_rule() -> None:
    scenario = TestScenario.model_validate(scenario_payload())
    task = build_browser_use_task(
        scenario,
        target_app_url="http://localhost:3000/",
        include_login_guidance=True,
    )

    assert "You are testing 4ga Boards at http://localhost:3000/" in task
    assert "4gaboards.com" not in task
    assert "Stay within the configured target application." in task


def test_task_builder_rejects_sensitive_key_inside_steps() -> None:
    payload = scenario_payload()
    payload["steps"] = [{"order": 1, "action": "输入 password 明文"}]
    scenario = TestScenario.model_validate(payload)

    with pytest.raises(ValueError, match="sensitive"):
        build_browser_use_task(scenario, target_app_url="https://demo.4gaboards.com/")


def test_sensitive_data_uses_browser_use_domain_scoped_shape_without_task_leak() -> None:
    settings = Settings(
        _env_file=None,
        target_app_url="http://localhost:3000/",
        browser_allowed_domains="*.4gaboards.com",
        fourga_username="alice@example.com",
        fourga_password="secret-password",
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
    )

    assert build_sensitive_data(settings) == {
        "*.4gaboards.com": {
            "FOURGA_USERNAME": "alice@example.com",
            "FOURGA_PASSWORD": "secret-password",
        },
        "http://localhost:3000": {
            "FOURGA_USERNAME": "alice@example.com",
            "FOURGA_PASSWORD": "secret-password",
        },
    }


def test_browser_session_is_local_managed_locked_down_and_not_cloud() -> None:
    settings = Settings(
        _env_file=None,
        target_app_url="https://demo.4gaboards.com/",
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
        browser_headless=True,
        browser_allowed_domains="*.4gaboards.com",
    )

    browser = create_browser_session(settings)

    assert browser.browser_profile.headless is True
    assert browser.browser_profile.allowed_domains == ["*.4gaboards.com"]
    assert browser.browser_profile.user_data_dir is not None
    assert "browser-use-user-data-dir-" in str(browser.browser_profile.user_data_dir)
    assert browser.browser_profile.use_cloud is False
    assert browser.browser_profile.cdp_url is None


def test_browser_session_allows_configured_local_target_origin() -> None:
    settings = Settings(
        _env_file=None,
        target_app_url="http://localhost:3000/",
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
        browser_headless=True,
        browser_allowed_domains="*.4gaboards.com",
    )

    browser = create_browser_session(settings)

    assert browser.browser_profile.allowed_domains == [
        "*.4gaboards.com",
        "http://localhost:3000",
    ]


def test_initial_actions_open_exact_target_url_before_llm_steps() -> None:
    settings = Settings(
        _env_file=None,
        target_app_url="http://localhost:3000/",
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
    )

    assert build_initial_actions(settings) == [
        {"navigate": {"url": "http://localhost:3000/", "new_tab": False}}
    ]


def test_effective_max_steps_raises_legacy_simple_scenario_to_configured_floor() -> None:
    scenario = TestScenario.model_validate(scenario_payload())
    settings = Settings(
        _env_file=None,
        max_scenario_steps=20,
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
    )

    assert effective_max_steps(scenario, settings) == 20


def test_effective_max_steps_keeps_harder_scenario_limit() -> None:
    payload = scenario_payload()
    payload["difficulty"] = "hard"
    payload["max_steps"] = 35
    scenario = TestScenario.model_validate(payload)
    settings = Settings(
        _env_file=None,
        max_scenario_steps=20,
        deepseek_api_key="deepseek-key",
        browser_use_api_key=None,
    )

    assert effective_max_steps(scenario, settings) == 35
