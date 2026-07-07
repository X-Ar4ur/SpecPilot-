from __future__ import annotations

import hashlib
import re
import textwrap
from dataclasses import dataclass
from typing import Any

from specpilot_backend.ingestion.classifier import classify_ui_operational

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


@dataclass(frozen=True)
class ManualChunk:
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _Section:
    level: int
    title: str
    body: str
    heading_path: tuple[str, ...]


def chunk_markdown(
    markdown: str,
    *,
    page_url: str,
    page_title: str,
    manual_section: str,
    module: str,
    module_variant: str | None = None,
    language: str = "en",
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[ManualChunk]:
    markdown = textwrap.dedent(markdown)
    sections = _split_by_headings(markdown, page_title=page_title)
    chunks: list[ManualChunk] = []

    for section in sections:
        section_chunks = _split_words(section.body, chunk_size=chunk_size, overlap=overlap)
        for split_index, content in enumerate(section_chunks):
            anchor = slugify(section.title) if section.level > 1 else ""
            heading_path = " / ".join((manual_section, *section.heading_path))
            source_url = f"{page_url}#{anchor}" if anchor else page_url
            classification = classify_ui_operational(
                content,
                url=source_url,
                heading_path=heading_path,
                module_hint=module,
            )
            metadata: dict[str, Any] = {
                "source_url": source_url,
                "page_url": page_url,
                "page_title": page_title,
                "heading_path": heading_path,
                "section_anchor": anchor,
                "content_hash": content_hash(content),
                "manual_section": manual_section,
                "module": classification.module,
                "module_variant": module_variant,
                "is_ui_operational": classification.is_ui_operational,
                "ui_operational_reason": classification.reason,
                "section_level": section.level,
                "chunk_index_in_page": len(chunks),
                "chunk_split_index": split_index,
                "language": language,
            }
            chunks.append(ManualChunk(content=content, metadata=metadata))
    return chunks


def content_hash(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")


def _split_by_headings(markdown: str, *, page_title: str) -> list[_Section]:
    markdown = re.sub(r"(?<=\))(?=#{1,3}\s)", "\n", markdown)
    lines = [line.rstrip() for line in markdown.splitlines()]
    sections: list[_Section] = []
    heading_stack: list[tuple[int, str]] = [(1, page_title)]
    current_level = 1
    current_title = page_title
    current_body: list[str] = []

    def flush() -> None:
        body = _section_body(current_level, current_title, current_body)
        if body:
            sections.append(
                _Section(
                    level=current_level,
                    title=current_title,
                    body=body,
                    heading_path=tuple(title for _, title in heading_stack),
                )
            )

    for line in lines:
        match = HEADING_RE.match(line)
        if not match:
            current_body.append(line)
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        flush()
        heading_stack = [(lvl, text) for lvl, text in heading_stack if lvl < level]
        heading_stack.append((level, title))
        current_level = level
        current_title = title
        current_body = []

    flush()
    return [section for section in sections if section.level > 1] or sections


def _section_body(level: int, title: str, body_lines: list[str]) -> str:
    body = "\n".join(body_lines).strip()
    if level <= 1:
        return body
    title_text = _plain_heading_text(title)
    if not title_text:
        return body
    if not body:
        return title_text
    return f"{title_text}\n\n{body}"


def _plain_heading_text(title: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
    text = text.replace("📄️", "")
    return re.sub(r"\s+", " ", text).strip()


def _split_words(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    words = normalized.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [normalized]

    if overlap >= chunk_size:
        msg = "overlap must be smaller than chunk_size"
        raise ValueError(msg)

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks
