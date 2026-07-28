from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from PIL import Image

from epub_a4_word.cover.fonts import font_candidates, resolve_font
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
)
from epub_a4_word.cover.print_plan import build_print_plan
from epub_a4_word.cover.render import (
    mm_to_px,
    render_preview,
    render_print_page,
    render_spread,
)
from epub_a4_word.cover.templates import apply_template, assign_publisher_logo


def _pixel_rgb(image: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    pixel = image.convert("RGB").getpixel((x, y))
    return tuple(pixel)


def test_spread_pixel_size_matches_mm(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    image = render_spread(project, dpi=300)
    layout = calculate_layout(project)
    assert image.width == round(layout.bleed_rect.width_mm / 25.4 * 300)
    assert image.height == round(layout.bleed_rect.height_mm / 25.4 * 300)


def test_spread_draws_full_crop_frame_and_respects_switch(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    dpi = 100
    x = mm_to_px(layout.spread_rect.x_mm, dpi)
    y = mm_to_px(
        layout.spread_rect.y_mm + layout.spread_rect.height_mm / 2.0,
        dpi,
    )

    shown = render_spread(project, dpi=dpi).convert("RGB")
    hidden_project = replace(
        project,
        export_settings=replace(
            project.export_settings,
            show_crop_marks=False,
        ),
    )
    hidden = render_spread(hidden_project, dpi=dpi).convert("RGB")

    assert max(shown.getpixel((x, y))) < 40
    assert min(hidden.getpixel((x, y))) > 240


def test_front_only_image_does_not_paint_back(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    source = tmp_path / "red.png"
    Image.new("RGB", (40, 40), "red").save(source)
    image_element = CoverElement(
        id="front-image",
        kind=ElementKind.IMAGE,
        region=Region.FRONT,
        transform=ElementTransform(
            layout.front_rect.x_mm,
            layout.front_rect.y_mm,
            layout.front_rect.width_mm,
            layout.front_rect.height_mm,
        ),
        content={"path": str(source), "fit": "cover"},
    )
    project = replace(project, elements=(image_element,))

    image = render_spread(project, dpi=100)
    back_x = mm_to_px(layout.back_rect.x_mm + 5.0, 100)
    front_x = mm_to_px(layout.front_rect.x_mm + 5.0, 100)
    y = mm_to_px(layout.front_rect.y_mm + 5.0, 100)
    assert _pixel_rgb(image, back_x, y) == (255, 255, 255)
    assert _pixel_rgb(image, front_x, y)[0] > 240
    assert _pixel_rgb(image, front_x, y)[1] < 20


def test_publisher_logo_renders_on_back_in_front_only_mode(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    source = tmp_path / "publisher-logo.png"
    Image.new("RGB", (40, 40), "red").save(source)
    project = assign_publisher_logo(
        apply_template(sample_project(), "publisher_back_matter"),
        source,
    )
    logo = project.elements_by_id["back-publisher-logo"]

    image = render_spread(project, dpi=100)
    x = mm_to_px(logo.transform.x_mm + logo.transform.width_mm / 2.0, 100)
    y = mm_to_px(logo.transform.y_mm + logo.transform.height_mm / 2.0, 100)

    assert _pixel_rgb(image, x, y) == (255, 0, 0)


def test_preview_caps_longest_edge(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    result = render_preview(sample_project(), tmp_path / "preview.png", max_px=900)
    assert result.path == tmp_path / "preview.png"
    assert result.path.is_file()
    assert max(result.width_px, result.height_px) == 900


def test_equal_z_index_uses_stable_element_order(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    rect = layout.front_safe_rect
    red = CoverElement(
        id="first-red",
        kind=ElementKind.SHAPE,
        region=Region.FRONT,
        transform=ElementTransform(rect.x_mm, rect.y_mm, rect.width_mm, rect.height_mm),
        z_index=5,
        content={"fill": "#ff0000"},
    )
    blue = replace(red, id="second-blue", content={"fill": "#0000ff"})
    image = render_spread(replace(project, elements=(red, blue)), dpi=100)
    x = mm_to_px(rect.x_mm + rect.width_mm / 2.0, 100)
    y = mm_to_px(rect.y_mm + rect.height_mm / 2.0, 100)
    assert _pixel_rgb(image, x, y) == (0, 0, 255)


def test_non_printable_guides_are_omitted(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    rect = layout.front_safe_rect
    guide = CoverElement(
        id="guide",
        kind=ElementKind.GUIDE,
        region=Region.FRONT,
        transform=ElementTransform(rect.x_mm, rect.y_mm, rect.width_mm, rect.height_mm),
        content={"fill": "#ff0000", "printable": False},
    )
    image = render_spread(replace(project, elements=(guide,)), dpi=100)
    x = mm_to_px(rect.x_mm + 1.0, 100)
    y = mm_to_px(rect.y_mm + 1.0, 100)
    assert _pixel_rgb(image, x, y) == (255, 255, 255)


def test_print_page_has_exact_a4_pixel_size(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project(trim=(105.0, 148.0))
    page = build_print_plan(calculate_layout(project)).pages[0]
    image = render_print_page(project, page, dpi=100)
    assert image.size == (
        mm_to_px(page.paper_size_mm[0], 100),
        mm_to_px(page.paper_size_mm[1], 100),
    )


def test_text_overflow_is_reported_in_preview(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    text = CoverElement(
        id="overflow-text",
        kind=ElementKind.TEXT,
        region=Region.FRONT,
        transform=ElementTransform(
            layout.front_safe_rect.x_mm,
            layout.front_safe_rect.y_mm,
            10.0,
            3.0,
        ),
        content={
            "text": "這是一段一定無法放進極小文字框的長文字",
            "font_family": "sans-serif",
            "font_size_pt": 18.0,
            "color": "#111111",
        },
    )
    result = render_preview(
        replace(project, elements=(text,)), tmp_path / "overflow.png", max_px=600
    )
    assert any("overflow-text" in warning for warning in result.warnings)


def test_vertical_text_newline_starts_a_new_column(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    text = CoverElement(
        id="two-vertical-columns",
        kind=ElementKind.TEXT,
        region=Region.BACK,
        transform=ElementTransform(
            layout.back_safe_rect.x_mm,
            layout.back_safe_rect.y_mm,
            12.0,
            20.0,
        ),
        content={
            "text": "甲乙丙丁\n戊己庚辛",
            "font_family": "sans-serif",
            "font_size_pt": 12.0,
            "color": "#111111",
            "direction": "vertical",
        },
    )

    result = render_preview(
        replace(project, elements=(text,)),
        tmp_path / "vertical-columns.png",
        max_px=900,
    )

    assert not any("two-vertical-columns" in warning for warning in result.warnings)


def test_font_fallback_returns_a_usable_font() -> None:
    font = resolve_font("missing-family", None, 18)
    assert font is not None


def test_font_fallback_candidates_include_cjk_system_fonts() -> None:
    candidates = tuple(str(path).replace("\\", "/") for path in font_candidates(None))
    assert any(path.endswith("/Windows/Fonts/msjh.ttc") for path in candidates)
    assert any(path.endswith("/system/fonts/NotoSansCJK-Regular.ttc") for path in candidates)


def test_full_spread_image_mode_uses_bleed_rect_even_for_front_region(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project()
    layout = calculate_layout(project)
    source = tmp_path / "blue.png"
    Image.new("RGB", (40, 40), "blue").save(source)
    image_element = CoverElement(
        id="spread-image",
        kind=ElementKind.IMAGE,
        region=Region.FRONT,
        transform=ElementTransform(
            layout.bleed_rect.x_mm,
            layout.bleed_rect.y_mm,
            layout.bleed_rect.width_mm,
            layout.bleed_rect.height_mm,
        ),
        content={"path": str(source), "fit": "cover"},
    )
    project = replace(
        project,
        image_mode=ImageMode.FULL_SPREAD,
        elements=(image_element,),
    )
    image = render_spread(project, dpi=100)
    back_x = mm_to_px(layout.back_rect.x_mm + 5.0, 100)
    y = mm_to_px(layout.back_rect.y_mm + 5.0, 100)
    assert _pixel_rgb(image, back_x, y) == (0, 0, 255)


def test_two_page_print_marks_use_readable_labels_and_instructions(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project(trim=(148.0, 210.0))
    plan = build_print_plan(calculate_layout(project))

    labels = [
        mark.label
        for page in plan.pages
        for mark in page.marks
        if mark.kind == "label"
    ]
    assert "第 1 頁／2：封底側" in labels
    assert "第 2 頁／2：正面側" in labels
    assert "100% 實際大小列印，請關閉「符合紙張大小」" in labels
    assert "重疊黏貼區" in labels

    for page in plan.pages:
        rendered = render_print_page(project, page, dpi=100)
        assert rendered.size == (
            mm_to_px(page.paper_size_mm[0], 100),
            mm_to_px(page.paper_size_mm[1], 100),
        )
