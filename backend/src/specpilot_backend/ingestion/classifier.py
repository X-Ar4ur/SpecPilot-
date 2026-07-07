from dataclasses import dataclass

UI_OPERATIONAL_CLASSIFIER_PROMPT = """Decide whether a 4ga Boards manual chunk describes UI operations relevant to testing.

Input:
- URL: {url}
- Heading path: {heading_path}
- Chunk text:
{chunk_text}

Return only JSON:
{{
  "is_ui_operational": true,
  "module": "Card",
  "reason": "The chunk describes creating and editing cards through the UI."
}}

Rules:
- Return false for developer APIs, deployment, database schema, CLI commands, package installation, and environment variables.
- Return true for user-visible UI operations, settings, permissions, navigation, board/list/card operations, views, and admin UI flows.
"""

TECHNICAL_TERMS = {
    "api",
    "api reference",
    "deployment",
    "database",
    "schema",
    "cli",
    "command line",
    "package install",
    "installation command",
    "environment variable",
    "docker",
    "kubernetes",
    "migration",
}

UI_TERMS = {
    "admin",
    "board",
    "card",
    "click",
    "create",
    "delete",
    "edit",
    "filter",
    "import",
    "list",
    "menu",
    "move",
    "navigation",
    "notification",
    "permission",
    "project",
    "search",
    "setting",
    "sidebar",
    "switch",
    "user",
    "view",
}

MODULE_HINTS = {
    "Project": ("project", "workspace"),
    "Board": ("board",),
    "List": ("list", "swimlane"),
    "Card": ("card", "task"),
    "Views": ("view", "calendar", "timeline", "kanban"),
    "Settings": ("setting", "permission", "role", "user", "admin"),
}


@dataclass(frozen=True)
class UIOperationalClassification:
    is_ui_operational: bool
    module: str
    reason: str


def build_ui_operational_prompt(url: str, heading_path: str, chunk_text: str) -> str:
    return UI_OPERATIONAL_CLASSIFIER_PROMPT.format(
        url=url,
        heading_path=heading_path,
        chunk_text=chunk_text,
    )


def classify_ui_operational(
    chunk_text: str,
    *,
    url: str,
    heading_path: str,
    module_hint: str = "Other",
) -> UIOperationalClassification:
    haystack = f"{url} {heading_path} {chunk_text}".lower()
    technical_hits = sorted(term for term in TECHNICAL_TERMS if term in haystack)
    ui_hits = sorted(term for term in UI_TERMS if term in haystack)

    if technical_hits and not ui_hits:
        return UIOperationalClassification(
            is_ui_operational=False,
            module=module_hint,
            reason=f"Technical documentation terms found: {', '.join(technical_hits)}.",
        )
    if ui_hits:
        return UIOperationalClassification(
            is_ui_operational=True,
            module=_infer_module(haystack, module_hint),
            reason=f"UI operation terms found: {', '.join(ui_hits[:4])}.",
        )
    return UIOperationalClassification(
        is_ui_operational=False,
        module=module_hint,
        reason="No clear user-visible UI operation signal was found.",
    )


def _infer_module(haystack: str, module_hint: str) -> str:
    if module_hint != "Other":
        return module_hint
    for module, terms in MODULE_HINTS.items():
        if any(term in haystack for term in terms):
            return module
    return "Other"
