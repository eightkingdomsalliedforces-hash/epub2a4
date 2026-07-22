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
