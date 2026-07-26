from pathlib import Path

from epub_a4_word.epub import parse_epub
from epub_a4_word.models import ImageBlock, TextBlock


def test_parse_epub_uses_spine_order_and_metadata(sample_epub: Path) -> None:
    book = parse_epub(sample_epub)

    assert book.title == "測試小說"
    assert book.author == "測試作者"
    texts = [block.text for block in book.blocks if isinstance(block, TextBlock)]
    assert texts.index("第二章") < texts.index("第一章")
    assert texts.index("先出現的段落，包含 粗體 和 斜體。") < texts.index("後出現的段落。")


def test_parse_epub_preserves_inline_styles_and_image_resource(sample_epub: Path) -> None:
    book = parse_epub(sample_epub)

    paragraph = next(
        block for block in book.blocks
        if isinstance(block, TextBlock) and block.text.startswith("先出現")
    )
    assert any(run.bold and run.text == "粗體" for run in paragraph.runs)
    assert any(run.italic and run.text == "斜體" for run in paragraph.runs)

    image = next(block for block in book.blocks if isinstance(block, ImageBlock))
    assert image.resource_path == "OEBPS/Images/pic.png"
    assert image.alt_text == "插圖"
    assert book.resources[image.resource_path].startswith(b"\x89PNG")


def test_nested_container_keeps_block_and_image_order(sample_epub: Path) -> None:
    book = parse_epub(sample_epub)
    significant = [
        block.text if isinstance(block, TextBlock) else block.resource_path
        for block in book.blocks
        if isinstance(block, (TextBlock, ImageBlock))
    ]
    assert significant.index("先出現的段落，包含 粗體 和 斜體。") < significant.index("OEBPS/Images/pic.png")
    assert significant.index("OEBPS/Images/pic.png") < significant.index("圖片後面的段落。")


def test_parse_epub_defaults_to_body_only_and_removes_high_confidence_covers(
    cover_epub_factory,
) -> None:
    from epub_a4_word.models import PageBreakBlock

    book = parse_epub(cover_epub_factory())

    texts = [block.text for block in book.blocks if isinstance(block, TextBlock)]
    images = [block.resource_path for block in book.blocks if isinstance(block, ImageBlock)]
    assert texts == ["第一章", "唯一正文內容。"]
    assert images == []
    assert not book.blocks or not isinstance(book.blocks[0], PageBreakBlock)
    assert not book.blocks or not isinstance(book.blocks[-1], PageBreakBlock)
    assert not any(
        isinstance(first, PageBreakBlock) and isinstance(second, PageBreakBlock)
        for first, second in zip(book.blocks, book.blocks[1:])
    )


def test_parse_epub_can_preserve_original_cover_pages(cover_epub_factory) -> None:
    from epub_a4_word.models import PageBreakBlock

    book = parse_epub(cover_epub_factory(), content_only=False)

    images = [block.resource_path for block in book.blocks if isinstance(block, ImageBlock)]
    assert images == ["OEBPS/Images/front.png", "OEBPS/Images/back.png"]
    assert sum(isinstance(block, PageBreakBlock) for block in book.blocks) == 2


def test_medium_back_cover_remains_until_user_confirms_it(cover_epub_factory) -> None:
    source = cover_epub_factory(generic_back=True)

    unconfirmed = parse_epub(source)
    confirmed = parse_epub(
        source,
        confirmed_back_cover_page="OEBPS/Text/plate.xhtml",
    )

    assert [block.resource_path for block in unconfirmed.blocks if isinstance(block, ImageBlock)] == [
        "OEBPS/Images/back.png"
    ]
    assert [block.resource_path for block in confirmed.blocks if isinstance(block, ImageBlock)] == []


def test_empty_spine_document_before_body_does_not_create_leading_page_break(
    cover_epub_factory,
) -> None:
    from epub_a4_word.models import PageBreakBlock

    book = parse_epub(cover_epub_factory(leading_empty=True))

    assert [block.text for block in book.blocks if isinstance(block, TextBlock)] == [
        "第一章",
        "唯一正文內容。",
    ]
    assert book.blocks
    assert not isinstance(book.blocks[0], PageBreakBlock)
