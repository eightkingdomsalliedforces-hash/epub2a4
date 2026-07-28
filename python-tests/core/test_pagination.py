from dataclasses import replace

import pytest

from epub_a4_word.models import ImageBlock, PageBreakBlock, TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, paginate, resolve_layout


def _body(text: str) -> TextBlock:
    return TextBlock((TextRun(text),), style="body")


def test_layout_direction_defaults_preserve_legacy_horizontal_behavior() -> None:
    settings = LayoutSettings()

    assert settings.writing_mode == "horizontal"
    assert settings.binding_direction == "left"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("writing_mode", "diagonal", "writing mode"),
        ("binding_direction", "middle", "binding direction"),
    ],
)
def test_resolve_layout_rejects_unknown_direction_values(
    field: str,
    value: str,
    message: str,
) -> None:
    settings = replace(LayoutSettings(), **{field: value})

    with pytest.raises(ValueError, match=message):
        resolve_layout(settings)


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


def test_vertical_pagination_keeps_mixed_text_in_source_order() -> None:
    text = "魔法禁書目錄 A Certain Magical Index 2026。" * 90
    settings = LayoutSettings(
        writing_mode="taiwan_vertical",
        binding_direction="right",
        content_width_pt=120,
        content_height_pt=220,
        page_numbers=False,
    )

    pages = paginate([_body(text)], settings, image_sizes={})

    rebuilt = "".join(
        block.text
        for page in pages
        for block in page.blocks
        if isinstance(block, TextBlock)
    )
    assert len(pages) > 1
    assert rebuilt == text
    assert all(page.used_points <= settings.content_width_pt + 0.01 for page in pages)


def test_vertical_page_height_controls_characters_per_column() -> None:
    tall = LayoutSettings(
        writing_mode="taiwan_vertical",
        content_width_pt=120,
        content_height_pt=260,
        page_numbers=False,
    )
    short = replace(tall, content_height_pt=130)
    text = _body("直排容量測試。" * 120)

    assert len(paginate([text], tall, {})) < len(paginate([text], short, {}))


def test_vertical_pagination_rejects_page_that_cannot_fit_one_character() -> None:
    settings = LayoutSettings(
        writing_mode="taiwan_vertical",
        content_width_pt=4,
        content_height_pt=4,
        body_font_pt=9,
        page_numbers=False,
    )

    with pytest.raises(ValueError, match="直排版面"):
        paginate([_body("字")], settings, {})


def test_vertical_pagination_preserves_styles_breaks_and_image_order() -> None:
    image = ImageBlock("Images/plate.png")
    blocks = [
        TextBlock((TextRun("第一章"),), style="heading"),
        _body("正文" * 100),
        TextBlock((TextRun("引文"),), style="quote"),
        PageBreakBlock(),
        image,
        _body("插圖後文字"),
    ]
    settings = LayoutSettings(
        writing_mode="taiwan_vertical",
        binding_direction="right",
        content_width_pt=150,
        content_height_pt=210,
        page_numbers=False,
    )

    pages = paginate(blocks, settings, {"Images/plate.png": (600, 900)})
    flattened = [block for page in pages for block in page.blocks]

    text_blocks = [block for block in flattened if isinstance(block, TextBlock)]
    assert text_blocks[0].style == "heading"
    assert next(index for index, block in enumerate(flattened) if block == image) < len(
        flattened
    ) - 1
    assert text_blocks[-1].text == "插圖後文字"


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


@pytest.mark.parametrize(
    "mode",
    ["single_a5", "single_4x6", "b6_on_a5", "four_up", "signature16"],
)
def test_mixed_text_never_exceeds_resolved_content_height(mode: str) -> None:
    settings = resolve_layout(LayoutSettings(imposition_mode=mode))
    block = TextBlock(
        (TextRun("魔法禁書目錄 A Certain Magical Index 測試段落。" * 180),),
        style="body",
    )

    pages = paginate((block,), settings, {})

    assert len(pages) >= 2
    assert all(page.used_points <= settings.content_height_pt for page in pages)


@pytest.mark.parametrize(
    ("mode", "minimum_safety"),
    [
        ("single_a5", 28.0),
        ("single_4x6", 28.0),
        ("b6_on_a5", 42.0),
        ("four_up", 24.0),
        ("signature16", 24.0),
    ],
)
def test_every_output_mode_reserves_word_bottom_safety(
    mode: str, minimum_safety: float
) -> None:
    without_safety = resolve_layout(
        LayoutSettings(imposition_mode=mode, pagination_safety_pt=0.0)
    )
    requested_more = resolve_layout(
        LayoutSettings(imposition_mode=mode, pagination_safety_pt=minimum_safety + 3.0)
    )

    assert without_safety.pagination_safety_pt == minimum_safety
    assert requested_more.pagination_safety_pt == minimum_safety + 3.0
