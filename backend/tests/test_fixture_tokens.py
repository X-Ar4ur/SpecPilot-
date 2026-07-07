from __future__ import annotations

from specpilot_backend.fixtures.tokens import (
    find_fixture_tokens,
    resolve_fixture_tokens,
    unresolved_fixture_tokens,
)


def test_find_tokens_across_nested_structures() -> None:
    value = {
        "steps": [{"action": "打开 {{fixture.target_card.title}}"}],
        "expectations": [{"params": {"text": "{{ fixture.target_card.title }}"}}],
        "noise": "no token here",
    }

    assert find_fixture_tokens(value) == {("target_card", "title")}


def test_resolve_replaces_known_tokens_and_keeps_unknown() -> None:
    value = {
        "action": "打开 {{fixture.target_card.title}}",
        "other": "{{fixture.missing.title}}",
    }
    resolved = {"target_card": {"title": "买菜清单"}}

    out = resolve_fixture_tokens(value, resolved)

    assert out["action"] == "打开 买菜清单"
    assert out["other"] == "{{fixture.missing.title}}"


def test_unresolved_tokens_reports_only_missing() -> None:
    value = "{{fixture.a.title}} and {{fixture.b.title}}"
    resolved = {"a": {"title": "X"}}

    assert unresolved_fixture_tokens(value, resolved) == {("b", "title")}
