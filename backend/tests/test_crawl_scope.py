from specpilot_backend.ingestion.crawler import (
    CrawlScope,
    discover_manual_links,
    infer_manual_metadata,
    is_allowed_manual_url,
    normalize_docs_url,
)


def test_crawl_scope_allows_only_english_user_and_admin_manual_pages() -> None:
    allowed = [
        "https://docs.4gaboards.com/docs/user-manual/boards/create-board",
        "https://docs.4gaboards.com/docs/admin-manual/users/permissions/",
        "https://docs.4gaboards.com/en/docs/user-manual/cards#create-card",
        "https://docs.4gaboards.com/docs/project",
        "https://docs.4gaboards.com/docs/project-settings",
    ]
    blocked = [
        "https://docs.4gaboards.com/pl/docs/user-manual/boards/create-board",
        "https://docs.4gaboards.com/docs/developer-manual/api",
        "https://docs.4gaboards.com/docs/getting-started",
        "https://docs.4gaboards.com/docs/intro",
        "https://docs.4gaboards.com/docs/user-manual/api-reference",
        "https://docs.4gaboards.com/docs/admin-manual/deployment",
        "https://docs.4gaboards.com/docs/admin-manual/database-schema",
        "https://docs.4gaboards.com/docs/user-manual/package-installation",
        "https://docs.4gaboards.com/docs/user-manual/cli-commands",
        "https://demo.4gaboards.com/docs/user-manual/boards",
    ]

    assert all(is_allowed_manual_url(url) for url in allowed)
    assert not any(is_allowed_manual_url(url) for url in blocked)


def test_normalize_docs_url_strips_fragment_query_and_trailing_slash() -> None:
    url = "https://docs.4gaboards.com/docs/user-manual/boards/?utm=x#create"

    assert (
        normalize_docs_url(url)
        == "https://docs.4gaboards.com/docs/user-manual/boards"
    )


def test_discover_manual_links_keeps_only_in_scope_links() -> None:
    html = """
    <a href="/docs/user-manual/boards/create-board">Create board</a>
    <a href="/docs/admin-manual/users/permissions">Permissions</a>
    <a href="/docs/project">Project</a>
    <a href="/docs/project-settings">Project Settings</a>
    <a href="/docs/getting-started">Getting Started</a>
    <a href="/pl/docs/user-manual/boards/create-board">Polish</a>
    <a href="/docs/developer-manual/api">API</a>
    <a href="/docs/user-manual/cli-commands">CLI</a>
    """
    links = discover_manual_links(
        html,
        page_url="https://docs.4gaboards.com/docs/user-manual/overview",
        scope=CrawlScope(),
    )

    assert links == [
        "https://docs.4gaboards.com/docs/user-manual/boards/create-board",
        "https://docs.4gaboards.com/docs/admin-manual/users/permissions",
        "https://docs.4gaboards.com/docs/project",
        "https://docs.4gaboards.com/docs/project-settings",
    ]


def test_infer_manual_metadata_uses_url_tokens_without_technical_pages() -> None:
    metadata = infer_manual_metadata(
        "https://docs.4gaboards.com/docs/user-manual/board/board-view"
    )

    assert metadata.manual_section == "user-manual"
    assert metadata.language == "en"
    assert metadata.module == "Board"
    assert metadata.module_variant == "board-view"


def test_infer_manual_metadata_handles_flat_docusaurus_manual_pages() -> None:
    user_metadata = infer_manual_metadata("https://docs.4gaboards.com/docs/project")
    admin_metadata = infer_manual_metadata(
        "https://docs.4gaboards.com/docs/project-settings"
    )

    assert user_metadata.manual_section == "user-manual"
    assert user_metadata.module == "Project"
    assert user_metadata.module_variant == "project"
    assert admin_metadata.manual_section == "admin-manual"
    assert admin_metadata.module == "Settings"
    assert admin_metadata.module_variant == "project-settings"
