from __future__ import annotations

import asyncio

from specpilot_backend.config import get_settings
from specpilot_backend.ingestion.chunker import chunk_markdown
from specpilot_backend.ingestion.cleaner import clean_markdown
from specpilot_backend.ingestion.crawler import CrawlScope, crawl_manual_pages
from specpilot_backend.ingestion.indexer import index_chunks


async def _run() -> None:
    settings = get_settings()
    scope = CrawlScope(base_url=settings.docs_base_url)
    start_urls = (
        "https://docs.4gaboards.com/docs/user-manual",
        "https://docs.4gaboards.com/docs/admin-manual",
    )
    pages = await crawl_manual_pages(start_urls, scope=scope)
    chunks = []
    for page in pages:
        chunks.extend(
            chunk_markdown(
                clean_markdown(page.markdown),
                page_url=page.url,
                page_title=page.title,
                manual_section=page.manual_section,
                module=page.module,
                module_variant=page.module_variant,
                language=page.language,
            )
        )
    indexed = index_chunks(chunks, persist_dir=settings.chroma_persist_dir)
    print(f"Indexed {indexed} chunks from {len(pages)} manual pages.")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
