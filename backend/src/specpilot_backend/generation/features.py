from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from specpilot_backend.generation.validators import validate_feature_payload
from specpilot_backend.ingestion.chunker import ManualChunk


def generate_feature_payloads(
    chunks: list[ManualChunk],
    *,
    persist: bool = False,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[ManualChunk]] = defaultdict(list)
    for chunk in chunks:
        if chunk.metadata.get("is_ui_operational") is False:
            continue
        module = str(chunk.metadata.get("module", "Other"))
        title = _feature_title(chunk)
        grouped[(module, title)].append(chunk)

    features: list[dict[str, Any]] = []
    for (module, title), source_chunks in sorted(grouped.items()):
        quote = _first_supported_quote(source_chunks[0].content)
        payload: dict[str, object] = {
            "feature_id": _feature_id(module, title),
            "module": module,
            "title": title,
            "summary": _summary_for(module, title),
            "source_urls": _source_urls(source_chunks),
            "evidence_quotes": [quote],
            "confidence": 0.75,
            "coverage_status": "uncovered",
        }
        validate_feature_payload(payload, source_chunks)
        features.append(payload)

    if persist:
        from specpilot_backend.services.persistence import save_feature_payload

        for feature in features:
            save_feature_payload(feature)
    return features


def _feature_title(chunk: ManualChunk) -> str:
    heading_path = str(chunk.metadata.get("heading_path", ""))
    title = heading_path.rsplit("/", maxsplit=1)[-1].strip()
    return title or str(chunk.metadata.get("page_title", "Other feature"))


def _feature_id(module: str, title: str) -> str:
    return f"ft_{_slug(module)}_{_slug(title)}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _summary_for(module: str, title: str) -> str:
    lowered = title.lower()
    if "create" in lowered and module == "Card":
        return "Users can create a card from a list."
    if "create" in lowered:
        return f"Users can create {module.lower()} items through the UI."
    if "edit" in lowered:
        return f"Users can edit {module.lower()} information through the UI."
    if "view" in lowered or module == "Views":
        return "Users can switch and inspect views through the UI."
    return f"Users can use {title.lower()} in the {module} module."


def _first_supported_quote(content: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", content.strip(), maxsplit=1)[0]
    words = sentence.split()
    if len(words) > 8:
        sentence = " ".join(words[:8])
    return sentence.rstrip(".,;:")


def _source_urls(chunks: list[ManualChunk]) -> list[str]:
    urls: list[str] = []
    for chunk in chunks:
        url = str(chunk.metadata["source_url"])
        if url not in urls:
            urls.append(url)
    return urls
