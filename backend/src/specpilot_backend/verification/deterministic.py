from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from specpilot_backend.models.scenarios import Expectation
from specpilot_backend.models.verification import VerificationResult


class VerificationSnapshot(BaseModel):
    """Read-only browser-use snapshot shared by verifier channels."""

    model_config = ConfigDict(extra="forbid")

    dom_text: str = ""
    current_url: str = ""
    html_snapshot: str = ""
    accessibility_tree: dict[str, Any] | list[Any] | str | None = None
    dom_summary: str = ""
    screenshot_initial_path: str | None = None
    screenshot_final_path: str | None = None


class CheckOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    reason: str
    evidence: dict[str, object] = Field(default_factory=dict)


def verify_expectation(
    expectation: Expectation,
    snapshot: VerificationSnapshot,
    *,
    expectation_index: int,
) -> VerificationResult:
    """Dispatch a zero-locator expectation to a deterministic snapshot check."""

    if expectation.type == "semantic":
        return VerificationResult(
            expectation_index=expectation_index,
            channel="deterministic",
            verdict="needs_review",
            confidence=0.0,
            reason="Semantic expectations are handled by VisionVerifier.",
            evidence={"expectation_type": expectation.type},
        )

    checkers = {
        "element_visible": check_element_visible,
        "text_present": check_text_present,
        "url_match": check_url_match,
        "element_state": check_element_state,
        "containment": check_containment,
    }
    checker = checkers[expectation.type]
    outcome = checker(expectation.params, snapshot)
    return VerificationResult(
        expectation_index=expectation_index,
        channel="deterministic",
        verdict="pass" if outcome.passed else "fail",
        confidence=1.0,
        reason=outcome.reason,
        evidence=outcome.evidence,
    )


def check_element_visible(
    params: dict[str, object], snapshot: VerificationSnapshot
) -> CheckOutcome:
    target = _required_text_param(params, "text")
    container = _optional_text_param(params, "container_text")
    text_found = _contains_text(_combined_visible_text(snapshot), target)

    if text_found and container is not None:
        text_found = _contains_text(_combined_visible_text(snapshot), container)
        if text_found:
            text_found = _a11y_contains(container, target, snapshot.accessibility_tree)

    return CheckOutcome(
        passed=text_found,
        reason=(
            f"Found visible text '{target}'."
            if text_found
            else f"Visible text '{target}' was not found."
        ),
        evidence={
            "expected_text": target,
            "container_text": container,
            "found": text_found,
        },
    )


def check_text_present(
    params: dict[str, object], snapshot: VerificationSnapshot
) -> CheckOutcome:
    target = _required_text_param(params, "text")
    not_present = bool(params.get("not_present", False))
    found = _contains_text(_combined_visible_text(snapshot), target)
    passed = not found if not_present else found
    reason = (
        f"Text '{target}' is absent as expected."
        if not_present and passed
        else f"Text '{target}' is present."
        if passed
        else f"Text '{target}' should be absent but was found."
        if not_present
        else f"Text '{target}' was not found."
    )
    return CheckOutcome(
        passed=passed,
        reason=reason,
        evidence={
            "expected_text": target,
            "not_present": not_present,
            "found": found,
        },
    )


def check_url_match(
    params: dict[str, object], snapshot: VerificationSnapshot
) -> CheckOutcome:
    url = snapshot.current_url
    evidence: dict[str, object] = {"actual_url": url}
    if "pattern" in params:
        pattern = _required_text_param(params, "pattern")
        matched = re.search(pattern, url) is not None
        evidence["pattern"] = pattern
    elif "contains" in params:
        contains = _required_text_param(params, "contains")
        matched = contains in url
        evidence["contains"] = contains
    elif "equals" in params:
        equals = _required_text_param(params, "equals")
        matched = url == equals
        evidence["equals"] = equals
    else:
        return CheckOutcome(
            passed=False,
            reason="URL expectation must include pattern, contains, or equals.",
            evidence=evidence,
        )

    return CheckOutcome(
        passed=matched,
        reason="Current URL matched expectation." if matched else "URL did not match.",
        evidence=evidence | {"matched": matched},
    )


def check_element_state(
    params: dict[str, object], snapshot: VerificationSnapshot
) -> CheckOutcome:
    element_text = _required_text_param(params, "element_text")
    state = _required_text_param(params, "state").lower()
    actual_state = _state_from_accessibility(
        element_text, state, snapshot.accessibility_tree
    )
    if actual_state is None:
        actual_state = _state_from_html(element_text, state, snapshot.html_snapshot)

    passed = actual_state is True
    return CheckOutcome(
        passed=passed,
        reason=(
            f"Element '{element_text}' state '{state}' matched."
            if passed
            else f"Element '{element_text}' state '{state}' did not match."
        ),
        evidence={
            "element_text": element_text,
            "expected_state": state,
            "matched": passed,
        },
    )


def check_containment(
    params: dict[str, object], snapshot: VerificationSnapshot
) -> CheckOutcome:
    child_text = _required_text_param(params, "child_text")
    parent_label = _required_text_param(params, "parent_label")
    contained = _a11y_contains(
        parent_label, child_text, snapshot.accessibility_tree
    ) or _html_contains(parent_label, child_text, snapshot.html_snapshot)
    if not contained:
        text = _combined_visible_text(snapshot)
        contained = _contains_text(text, parent_label) and _contains_text(
            text, child_text
        )

    return CheckOutcome(
        passed=contained,
        reason=(
            f"'{child_text}' is contained by '{parent_label}'."
            if contained
            else f"'{child_text}' was not found inside '{parent_label}'."
        ),
        evidence={
            "child_text": child_text,
            "parent_label": parent_label,
            "contained": contained,
        },
    )


def _required_text_param(params: dict[str, object], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or value == "":
        msg = f"Expectation params must include non-empty '{key}'."
        raise ValueError(msg)
    return value


def _optional_text_param(params: dict[str, object], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or value == "":
        msg = f"Expectation param '{key}' must be a non-empty string."
        raise ValueError(msg)
    return value


def _combined_visible_text(snapshot: VerificationSnapshot) -> str:
    parts = [
        snapshot.dom_text,
        snapshot.dom_summary,
        _strip_markup(snapshot.html_snapshot),
        _a11y_text(snapshot.accessibility_tree),
    ]
    return "\n".join(part for part in parts if part)


def _contains_text(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _strip_markup(html_snapshot: str) -> str:
    return re.sub(r"<[^>]+>", " ", html_snapshot)


def _a11y_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [
            str(value.get("name", "")),
            str(value.get("value", "")),
            str(value.get("role", "")),
        ]
        parts.extend(_a11y_text(child) for child in value.get("children", []))
        return "\n".join(part for part in parts if part)
    if isinstance(value, list):
        return "\n".join(_a11y_text(item) for item in value)
    return json.dumps(value, ensure_ascii=False, default=str)


def _a11y_contains(parent_text: str, child_text: str, value: Any) -> bool:
    for node in _walk_a11y(value):
        node_text = _a11y_text(node)
        if _contains_text(node_text, parent_text) and _contains_text(
            node_text, child_text
        ):
            return True
    return False


def _walk_a11y(value: Any) -> list[Any]:
    nodes = [value]
    if isinstance(value, dict):
        for child in value.get("children", []):
            nodes.extend(_walk_a11y(child))
    elif isinstance(value, list):
        for item in value:
            nodes.extend(_walk_a11y(item))
    return nodes


def _html_contains(parent_label: str, child_text: str, html_snapshot: str) -> bool:
    lower_html = html_snapshot.casefold()
    parent_index = lower_html.find(parent_label.casefold())
    child_index = lower_html.find(child_text.casefold(), max(parent_index, 0))
    return parent_index >= 0 and child_index > parent_index


def _state_from_accessibility(element_text: str, state: str, value: Any) -> bool | None:
    for node in _walk_a11y(value):
        if not isinstance(node, dict):
            continue
        if not _contains_text(_a11y_text(node), element_text):
            continue
        if state in {"pressed", "selected", "checked", "expanded", "disabled"}:
            raw_value = node.get(state)
            if isinstance(raw_value, bool):
                return raw_value
        if state == "enabled" and isinstance(node.get("disabled"), bool):
            return not node["disabled"]
        if state == "collapsed" and isinstance(node.get("expanded"), bool):
            return not node["expanded"]
        if state == "unchecked" and isinstance(node.get("checked"), bool):
            return not node["checked"]
    return None


def _state_from_html(element_text: str, state: str, html_snapshot: str) -> bool | None:
    if not html_snapshot:
        return None
    lower_html = html_snapshot.casefold()
    text_index = lower_html.find(element_text.casefold())
    if text_index < 0:
        return None
    window_start = max(0, text_index - 320)
    window_end = min(len(lower_html), text_index + 320)
    window = lower_html[window_start:window_end]
    truthy_attributes = {
        "pressed": ['aria-pressed="true"', "aria-pressed='true'"],
        "selected": ['aria-selected="true"', "aria-selected='true'", " selected"],
        "checked": ['aria-checked="true"', "aria-checked='true'", " checked"],
        "expanded": ['aria-expanded="true"', "aria-expanded='true'"],
        "disabled": [" disabled", 'aria-disabled="true"', "aria-disabled='true'"],
    }
    falsy_attributes = {
        "enabled": [" disabled", 'aria-disabled="true"', "aria-disabled='true'"],
        "unchecked": ['aria-checked="true"', "aria-checked='true'", " checked"],
        "collapsed": ['aria-expanded="true"', "aria-expanded='true'"],
    }
    if state in truthy_attributes:
        return any(token in window for token in truthy_attributes[state])
    if state in falsy_attributes:
        return not any(token in window for token in falsy_attributes[state])
    return None
