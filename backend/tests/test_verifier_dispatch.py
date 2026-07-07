import inspect

from specpilot_backend.models.scenarios import Expectation
from specpilot_backend.verification import deterministic
from specpilot_backend.verification.arbitration import arbitrate_expectation
from specpilot_backend.verification.deterministic import (
    VerificationSnapshot,
    verify_expectation,
)


def sample_snapshot() -> VerificationSnapshot:
    return VerificationSnapshot(
        dom_text="Board Alpha\nTo Do\nQuarterly report\nBoard view",
        current_url="https://demo.4gaboards.com/boards/alpha",
        html_snapshot=(
            '<main aria-label="Board Alpha">'
            '<section aria-label="To Do">'
            "<article>Quarterly report</article>"
            "</section>"
            '<button aria-pressed="true">Board view</button>'
            "</main>"
        ),
        accessibility_tree={
            "role": "main",
            "name": "Board Alpha",
            "children": [
                {
                    "role": "list",
                    "name": "To Do",
                    "children": [{"role": "article", "name": "Quarterly report"}],
                },
                {"role": "button", "name": "Board view", "pressed": True},
            ],
        },
    )


def test_deterministic_verifier_dispatches_supported_expectation_types() -> None:
    snapshot = sample_snapshot()
    expectations = [
        Expectation(
            type="text_present",
            description="The created card title is visible.",
            params={"text": "Quarterly report"},
        ),
        Expectation(
            type="element_visible",
            description="The board view control is visible.",
            params={"text": "Board view"},
        ),
        Expectation(
            type="url_match",
            description="The user remains on the board page.",
            params={"contains": "/boards/alpha"},
        ),
        Expectation(
            type="element_state",
            description="The board view control is pressed.",
            params={"element_text": "Board view", "state": "pressed"},
        ),
        Expectation(
            type="containment",
            description="The new card is in the To Do list.",
            params={"child_text": "Quarterly report", "parent_label": "To Do"},
        ),
    ]

    results = [
        verify_expectation(expectation, snapshot, expectation_index=index)
        for index, expectation in enumerate(expectations)
    ]

    assert [result.verdict for result in results] == ["pass"] * len(expectations)
    assert all(result.channel == "deterministic" for result in results)


def test_text_absence_and_missing_text_fail_with_evidence() -> None:
    result = verify_expectation(
        Expectation(
            type="text_present",
            description="Missing card should be visible.",
            params={"text": "Missing card"},
        ),
        sample_snapshot(),
        expectation_index=0,
    )

    assert result.verdict == "fail"
    assert result.evidence["expected_text"] == "Missing card"
    assert result.evidence["found"] is False


def test_semantic_expectations_are_not_deterministically_passed() -> None:
    result = verify_expectation(
        Expectation(
            type="semantic",
            description="The board visually shows a successful drag operation.",
            params={},
        ),
        sample_snapshot(),
        expectation_index=0,
    )

    assert result.verdict == "needs_review"
    assert "VisionVerifier" in result.reason


def test_agent_self_reported_success_cannot_override_failed_verification() -> None:
    deterministic_result = verify_expectation(
        Expectation(
            type="text_present",
            description="Missing card should be visible.",
            params={"text": "Missing card"},
        ),
        sample_snapshot(),
        expectation_index=0,
    )

    result = arbitrate_expectation(
        expectation_type="text_present",
        deterministic_result=deterministic_result,
        vision_result=None,
        requires_visual_check=False,
        agent_self_reported_success=True,
    )

    assert result.final_verdict == "fail"
    assert result.label == "fail"


def test_deterministic_verifier_does_not_import_playwright_or_locator_apis() -> None:
    source = inspect.getsource(deterministic)

    assert "playwright" not in source.lower()
    assert ".locator(" not in source.lower()
    assert "page." not in source.lower()
