from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse, urlunparse

ALLOWED_HOST = "docs.4gaboards.com"
ALLOWED_SECTIONS = frozenset({"user-manual", "admin-manual"})
FLAT_MANUAL_PAGES: dict[str, tuple[str, str]] = {
    "structure": ("user-manual", "Other"),
    "project": ("user-manual", "Project"),
    "board": ("user-manual", "Board"),
    "board-view": ("user-manual", "Board"),
    "list-view": ("user-manual", "Views"),
    "list": ("user-manual", "List"),
    "card": ("user-manual", "Card"),
    "sidebar": ("user-manual", "Other"),
    "notifications": ("user-manual", "Other"),
    "settings": ("user-manual", "Settings"),
    "view": ("user-manual", "Views"),
    "shortcuts": ("user-manual", "Other"),
    "admin-settings": ("admin-manual", "Admin"),
    "instance-settings": ("admin-manual", "Settings"),
    "project-settings": ("admin-manual", "Settings"),
}
BLOCKED_PATH_TERMS = (
    "developer-manual",
    "api",
    "deployment",
    "database",
    "schema",
    "package",
    "install",
    "installation",
    "cli",
    "command-line",
    "docker",
    "kubernetes",
)


@dataclass(frozen=True)
class CrawlScope:
    base_url: str = "https://docs.4gaboards.com/"
    sections: tuple[str, ...] = ("user-manual", "admin-manual")
    language: str = "en"


@dataclass(frozen=True)
class ManualUrlMetadata:
    manual_section: str
    module: str
    module_variant: str | None
    language: str


@dataclass(frozen=True)
class CrawledManualPage:
    url: str
    title: str
    markdown: str
    manual_section: str
    module: str
    module_variant: str | None
    language: str = "en"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.links.append(value)


def normalize_docs_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def is_allowed_manual_url(url: str, scope: CrawlScope | None = None) -> bool:
    scope = scope or CrawlScope()
    normalized = normalize_docs_url(url)
    parsed = urlparse(normalized)
    if parsed.netloc != ALLOWED_HOST:
        return False

    path_parts = [part for part in parsed.path.split("/") if part]
    language = "en"
    if path_parts and path_parts[0] in {"en", "pl"}:
        language = path_parts.pop(0)
    if language != scope.language:
        return False
    if not path_parts or path_parts[0] != "docs":
        return False

    sections = set(scope.sections) & ALLOWED_SECTIONS
    if len(path_parts) < 2:
        return False

    lowered_path = "/".join(path_parts).lower()
    if any(term in lowered_path for term in BLOCKED_PATH_TERMS):
        return False
    if path_parts[1] in sections:
        return True
    if len(path_parts) == 2 and path_parts[1] in FLAT_MANUAL_PAGES:
        manual_section, _ = FLAT_MANUAL_PAGES[path_parts[1]]
        return manual_section in sections
    return False


def discover_manual_links(
    html: str,
    *,
    page_url: str,
    scope: CrawlScope | None = None,
) -> list[str]:
    parser = _LinkParser()
    parser.feed(html)
    seen: set[str] = set()
    links: list[str] = []
    for href in (*parser.links, *_markdown_links(html)):
        absolute = normalize_docs_url(urljoin(page_url, href))
        if absolute in seen or not is_allowed_manual_url(absolute, scope):
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


def _markdown_links(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text)


def infer_manual_metadata(url: str) -> ManualUrlMetadata:
    if not is_allowed_manual_url(url):
        msg = f"URL is outside the allowed manual crawl scope: {url}"
        raise ValueError(msg)

    path_parts = [part for part in urlparse(normalize_docs_url(url)).path.split("/") if part]
    language = "en"
    if path_parts[0] == "en":
        path_parts = path_parts[1:]
    if path_parts[1] in FLAT_MANUAL_PAGES:
        manual_section, module = FLAT_MANUAL_PAGES[path_parts[1]]
        module_variant = path_parts[1]
    else:
        manual_section = path_parts[1]
        content_parts = path_parts[2:]
        module_variant = content_parts[-1] if content_parts else None
        module = _module_from_parts(content_parts, manual_section)
    return ManualUrlMetadata(
        manual_section=manual_section,
        module=module,
        module_variant=module_variant,
        language=language,
    )


async def crawl_manual_pages(
    start_urls: Iterable[str],
    *,
    scope: CrawlScope | None = None,
    fetch_markdown: Callable[[str], Awaitable[tuple[str, str]]] | None = None,
    max_pages: int = 250,
) -> list[CrawledManualPage]:
    scope = scope or CrawlScope()
    queue = [normalize_docs_url(url) for url in start_urls]
    visited: set[str] = set()
    pages: list[CrawledManualPage] = []

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited or not is_allowed_manual_url(url, scope):
            continue
        visited.add(url)
        title, markdown = await _fetch_markdown(url, fetch_markdown=fetch_markdown)
        metadata = infer_manual_metadata(url)
        pages.append(
            CrawledManualPage(
                url=url,
                title=title,
                markdown=markdown,
                manual_section=metadata.manual_section,
                module=metadata.module,
                module_variant=metadata.module_variant,
                language=metadata.language,
            )
        )
        queue.extend(discover_manual_links(markdown, page_url=url, scope=scope))
    return pages


async def _fetch_markdown(
    url: str,
    *,
    fetch_markdown: Callable[[str], Awaitable[tuple[str, str]]] | None,
) -> tuple[str, str]:
    if fetch_markdown is not None:
        return await fetch_markdown(url)

    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
    markdown = getattr(result, "markdown", "") or ""
    title = getattr(result, "title", "") or _title_from_url(url)
    return title, markdown


def _module_from_parts(parts: list[str], manual_section: str) -> str:
    text = " ".join(parts).lower()
    if "project" in text:
        return "Project"
    if "board" in text:
        return "Board"
    if "list" in text:
        return "List"
    if "card" in text:
        return "Card"
    if "view" in text:
        return "Views"
    if any(term in text for term in ("setting", "permission", "user", "role")):
        return "Settings"
    if manual_section == "admin-manual":
        return "Admin"
    return "Other"


def _title_from_url(url: str) -> str:
    tail = normalize_docs_url(url).rstrip("/").rsplit("/", maxsplit=1)[-1]
    return tail.replace("-", " ").title()
