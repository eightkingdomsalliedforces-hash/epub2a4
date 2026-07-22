from epub_a4_word.models import ImageBlock, PageBreakBlock, TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, paginate


def _body(text: str) -> TextBlock:
    return TextBlock((TextRun(text),), style="body")


def test_paginate_splits_long_cjk_paragraph_without_losing_text() -> None:
    text = "這是一段用來測試中文分頁的文字。" * 180
    settings = LayoutSettings(content_height_pt=120, content_width_pt=180, page_numbers=False)

    pages = paginate([_body(text)], settings, image_sizes={})

    assert len(pages) > 2
    rebuilt = "".join(
        block.text
        for page in pages
        for block in page.blocks
        if isinstance(block, TextBlock)
    )
    assert rebuilt == text
    assert all(page.used_points <= settings.content_height_pt + 0.01 for page in pages)


def test_explicit_page_break_starts_a_new_mini_page() -> None:
    settings = LayoutSettings(content_height_pt=300, content_width_pt=180, page_numbers=False)

    pages = paginate([_body("第一頁"), PageBreakBlock(), _body("第二頁")], settings, image_sizes={})

    assert len(pages) == 2
    assert pages[0].blocks[0].text == "第一頁"
    assert pages[1].blocks[0].text == "第二頁"


def test_image_moves_to_next_page_when_remaining_space_is_too_small() -> None:
    settings = LayoutSettings(content_height_pt=150, content_width_pt=180, page_numbers=False)
    image = ImageBlock("Images/tall.png")
    blocks = [_body("內容" * 160), image]

    pages = paginate(blocks, settings, image_sizes={"Images/tall.png": (400, 800)})

    image_page_index = next(i for i, page in enumerate(pages) if image in page.blocks)
    assert image_page_index > 0
    assert pages[image_page_index].blocks[0] == image
    assert pages[image_page_index].used_points <= settings.content_height_pt + 0.01


def test_page_numbers_start_at_prologue_and_continue_through_image_pages() -> None:
    settings = LayoutSettings(content_height_pt=220, content_width_pt=180, page_numbers=True)
    cover = ImageBlock("Images/cover.png")
    illustration = ImageBlock("Images/inside.png")
    blocks = [
        cover,
        PageBreakBlock(),
        TextBlock((TextRun("內容簡介"),), style="heading"),
        _body("簡介文字"),
        PageBreakBlock(),
        TextBlock((TextRun("序 章 關於少年"),), style="heading"),
        _body("序章正文"),
        PageBreakBlock(),
        illustration,
        PageBreakBlock(),
        _body("插圖後正文"),
    ]

    pages = paginate(
        blocks,
        settings,
        image_sizes={"Images/cover.png": (100, 150), "Images/inside.png": (100, 150)},
    )

    assert [page.logical_page_number for page in pages] == [None, None, 1, 2, 3]
    assert [page.has_text for page in pages] == [False, True, True, False, True]


def test_margin_presets_expand_content_area() -> None:
    from epub_a4_word.pagination import resolve_layout

    safe = resolve_layout(LayoutSettings(margin_mode="safe"))
    maximized = resolve_layout(LayoutSettings(margin_mode="maximized"))
    borderless = resolve_layout(LayoutSettings(margin_mode="borderless"))

    assert safe.outer_margin_cm == 0.5
    assert maximized.outer_margin_cm == 0.2
    assert borderless.outer_margin_cm == 0.0
    assert safe.content_width_pt < maximized.content_width_pt < borderless.content_width_pt
    assert safe.content_height_pt < maximized.content_height_pt < borderless.content_height_pt


def test_single_page_modes_resolve_exact_paper_and_one_by_one_grid() -> None:
    from epub_a4_word.pagination import resolve_layout

    a5 = resolve_layout(LayoutSettings(imposition_mode="single_a5", margin_mode="maximized"))
    photo = resolve_layout(LayoutSettings(imposition_mode="single_4x6", margin_mode="maximized"))

    assert a5.paper_width_cm == 14.8
    assert a5.paper_height_cm == 21.0
    assert a5.grid_rows == 1
    assert a5.grid_cols == 1
    assert photo.paper_width_cm == 10.16
    assert photo.paper_height_cm == 15.24
    assert photo.grid_rows == 1
    assert photo.grid_cols == 1
    assert a5.cell_width_cm > photo.cell_width_cm
    assert a5.cell_height_cm > photo.cell_height_cm
    assert a5.content_width_pt > photo.content_width_pt
    assert a5.content_height_pt > photo.content_height_pt
