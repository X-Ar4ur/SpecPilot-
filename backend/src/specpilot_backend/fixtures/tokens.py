from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Matches {{fixture.<ref>.<attr>}} with optional surrounding whitespace.
FIXTURE_TOKEN_RE = re.compile(
    r"\{\{\s*fixture\.([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*\}\}"
)

ResolvedFixtures = Mapping[str, Mapping[str, object]]


def find_fixture_tokens(value: Any) -> set[tuple[str, str]]:
    """Collect every (ref, attr) referenced by a fixture token in ``value``."""
    found: set[tuple[str, str]] = set()
    _collect(value, found)
    return found


def resolve_fixture_tokens(value: Any, resolved: ResolvedFixtures) -> Any:
    """Replace fixture tokens in strings using ``resolved`` (ref -> attrs).

    Unknown tokens are left untouched so callers can detect them with
    :func:`unresolved_fixture_tokens`.
    """
    if isinstance(value, str):
        return _replace_in_string(value, resolved)
    if isinstance(value, dict):
        return {key: resolve_fixture_tokens(item, resolved) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_fixture_tokens(item, resolved) for item in value]
    return value


def unresolved_fixture_tokens(
    value: Any, resolved: ResolvedFixtures
) -> set[tuple[str, str]]:
    """Return tokens in ``value`` that ``resolved`` cannot fill."""
    return {
        (ref, attr)
        for ref, attr in find_fixture_tokens(value)
        if attr not in (resolved.get(ref) or {})
    }


def _collect(value: Any, found: set[tuple[str, str]]) -> None:
    if isinstance(value, str):
        found.update(FIXTURE_TOKEN_RE.findall(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect(item, found)


def _replace_in_string(text: str, resolved: ResolvedFixtures) -> str:
    def _sub(match: re.Match[str]) -> str:
        ref, attr = match.group(1), match.group(2)
        attrs = resolved.get(ref)
        if attrs is not None and attr in attrs:
            return str(attrs[attr])
        return match.group(0)

    return FIXTURE_TOKEN_RE.sub(_sub, text)
