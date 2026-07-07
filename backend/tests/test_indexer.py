from types import SimpleNamespace

from specpilot_backend.ingestion.chunker import ManualChunk
from specpilot_backend.ingestion.indexer import index_chunks


class _FakeCollection:
    def __init__(self) -> None:
        self.ids: list[str] = []

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, object]],
    ) -> None:
        self.ids = ids


class _FakeClient:
    def __init__(self, collection: _FakeCollection) -> None:
        self.collection = collection

    def get_or_create_collection(
        self,
        *,
        name: str,
        embedding_function: object,
        metadata: dict[str, object],
    ) -> _FakeCollection:
        return self.collection


def test_index_chunks_generates_unique_ids_for_repeated_content_hashes(
    monkeypatch,
    tmp_path,
) -> None:
    collection = _FakeCollection()

    def fake_persistent_client(path: str) -> _FakeClient:
        return _FakeClient(collection)

    monkeypatch.setitem(
        __import__("sys").modules,
        "chromadb",
        SimpleNamespace(PersistentClient=fake_persistent_client),
    )
    chunks = [
        ManualChunk(
            content="Repeated Docusaurus boilerplate",
            metadata={
                "content_hash": "sha256:706c9724c6de19967fb0dfebabcdef",
                "source_url": "https://docs.4gaboards.com/docs/user-manual/a#intro",
                "page_url": "https://docs.4gaboards.com/docs/user-manual/a",
                "heading_path": "user-manual / A / Intro",
                "chunk_index_in_page": 0,
                "chunk_split_index": 0,
            },
        ),
        ManualChunk(
            content="Repeated Docusaurus boilerplate",
            metadata={
                "content_hash": "sha256:706c9724c6de19967fb0dfebabcdef",
                "source_url": "https://docs.4gaboards.com/docs/admin-manual/b#intro",
                "page_url": "https://docs.4gaboards.com/docs/admin-manual/b",
                "heading_path": "admin-manual / B / Intro",
                "chunk_index_in_page": 0,
                "chunk_split_index": 0,
            },
        ),
    ]

    assert index_chunks(chunks, persist_dir=tmp_path) == 2
    assert len(collection.ids) == 2
    assert len(set(collection.ids)) == 2
