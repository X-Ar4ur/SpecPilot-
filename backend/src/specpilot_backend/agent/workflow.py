from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from specpilot_backend.agent.browser_use_runner import run_scenario_with_browser_use
from specpilot_backend.agent.task_builder import build_browser_use_task
from specpilot_backend.config import Settings, get_settings
from specpilot_backend.models.scenarios import TestScenario


class RunWorkflowState(TypedDict):
    run_id: str
    scenario: TestScenario
    task: NotRequired[str]
    browser_use_result: NotRequired[dict[str, Any]]


async def scenario_loader_node(state: RunWorkflowState) -> RunWorkflowState:
    settings = get_settings()
    scenario = state["scenario"]
    return {
        **state,
        "task": build_browser_use_task(
            scenario,
            target_app_url=settings.target_app_url,
        ),
    }


async def browser_use_run_node(state: RunWorkflowState) -> RunWorkflowState:
    result = await run_scenario_with_browser_use(
        state["scenario"],
        run_id=state["run_id"],
    )
    return {**state, "browser_use_result": result.__dict__}


async def trace_collector_node(state: RunWorkflowState) -> RunWorkflowState:
    return state


def build_run_workflow(_: Settings | None = None) -> Any:
    graph = StateGraph(RunWorkflowState)
    graph.add_node("ScenarioLoader", scenario_loader_node)
    graph.add_node("BrowserUseRun", browser_use_run_node)
    graph.add_node("TraceCollector", trace_collector_node)
    graph.add_edge(START, "ScenarioLoader")
    graph.add_edge("ScenarioLoader", "BrowserUseRun")
    graph.add_edge("BrowserUseRun", "TraceCollector")
    graph.add_edge("TraceCollector", END)
    return graph.compile()
