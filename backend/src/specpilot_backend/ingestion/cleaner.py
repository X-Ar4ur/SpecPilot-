from __future__ import annotations

import re

FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_markdown(markdown: str) -> str:
    text = FRONTMATTER_RE.sub("", markdown)
    text = SCRIPT_STYLE_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
