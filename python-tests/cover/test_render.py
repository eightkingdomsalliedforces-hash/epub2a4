from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from PIL import Image

from epub_a4_word.cover.fonts import resolve_font
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


def test_font_fallback_returns_a_usable_font() -> None:
    font = resolve_font("missing-family", None, 18)
    assert font is not None


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
