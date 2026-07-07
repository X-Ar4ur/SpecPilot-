from specpilot_backend.ingestion.chunker import chunk_markdown


def test_chunk_markdown_splits_by_headings_and_preserves_metadata() -> None:
    markdown = """
    # Board: General

    Intro text.

    ## Creating a new board

    Open the Boards page and click Create board.

    ## Board view

    Users can switch the board view from the view menu.
    """

    chunks = chunk_markdown(
        markdown,
        page_url="https://docs.4gaboards.com/docs/user-manual/board",
        page_title="Board: General",
        manual_section="user-manual",
        module="Board",
    )

    assert [chunk.metadata["section_anchor"] for chunk in chunks] == [
        "creating-a-new-board",
        "board-view",
    ]
    assert chunks[0].metadata["source_url"].endswith("#creating-a-new-board")
    assert chunks[0].metadata["heading_path"] == (
        "user-manual / Board: General / Creating a new board"
    )
    assert chunks[0].metadata["language"] == "en"
    assert chunks[0].metadata["manual_section"] == "user-manual"
    assert chunks[0].metadata["module"] == "Board"
    assert chunks[0].metadata["content_hash"].startswith("sha256:")
    assert chunks[0].metadata["is_ui_operational"] is True


def test_chunk_markdown_uses_recursive_word_fallback_for_large_sections() -> None:
    long_text = " ".join(f"step{i}" for i in range(90))
    markdown = f"""
    # Card

    ## Editing a card

    {long_text}
    """

    chunks = chunk_markdown(
        markdown,
        page_url="https://docs.4gaboards.com/docs/user-manual/cards/edit",
        page_title="Card",
        manual_section="user-manual",
        module="Card",
        chunk_size=25,
        overlap=5,
    )

    assert len(chunks) > 1
    assert all(len(chunk.content.split()) <= 25 for chunk in chunks)
    assert chunks[1].content.split()[:5] == chunks[0].content.split()[-5:]
    assert [chunk.metadata["chunk_index_in_page"] for chunk in chunks] == list(
        range(len(chunks))
    )


def test_chunk_markdown_keeps_docusaurus_card_heading_text_as_evidence() -> None:
    markdown = """
    # For Users
    Learn how to get the most of 4ga Boards as a user!
    ## [ 📄️Project Projects are the highest structure of 4ga boards workflow. All of the projects can be accessed from the dashboard view (3) or using the sidebar (2).](https://docs.4gaboards.com/docs/project)## [ 📄️Board: General The heart of 4ga Boards is a board.](https://docs.4gaboards.com/docs/board)
    """

    chunks = chunk_markdown(
        markdown,
        page_url="https://docs.4gaboards.com/docs/user-manual",
        page_title="User Manual",
        manual_section="user-manual",
        module="Other",
    )

    assert len(chunks) >= 2
    assert any(
        "Projects are the highest structure of 4ga boards workflow" in chunk.content
        for chunk in chunks
    )
    assert any("The heart of 4ga Boards is a board" in chunk.content for chunk in chunks)
