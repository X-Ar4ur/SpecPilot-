from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from specpilot_backend.config import get_settings
from specpilot_backend.ingestion.chunker import ManualChunk


def index_chunks(
    chunks: Iterable[ManualChunk],
    *,
    persist_dir: Path | None = None,
    collection_name: str = "manual_chunks",
    embedding_function: Any | None = None,
) -> int:
    chunk_list = list(chunks)
    if not chunk_list:
        return 0

    import chromadb

    persist_dir = persist_dir or get_settings().chroma_persist_dir
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function,
        metadata={"description": "4ga Boards manual chunks"},
    )
    collection.upsert(
        ids=[_chunk_id(chunk) for chunk in chunk_list],
        documents=[chunk.content for chunk in chunk_list],
        metadatas=[_sanitize_metadata(chunk.metadata) for chunk in chunk_list],
    )
    return len(chunk_list)


def _chunk_id(chunk: ManualChunk) -> str:
    digest = str(chunk.metadata["content_hash"]).removeprefix("sha256:")
    identity_parts = (
        str(chunk.metadata.get("source_url", "")),
        str(chunk.metadata.get("heading_path", "")),
        str(chunk.metadata.get("chunk_index_in_page", "")),
        str(chunk.metadata.get("chunk_split_index", "")),
    )
    identity = hashlib.sha256("|".join(identity_parts).encode("utf-8")).hexdigest()
    return f"chunk_{digest[:24]}_{identity[:12]}"


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    sanitized: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized
