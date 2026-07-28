from __future__ import annotations

from dataclasses import replace

from PIL import Image

from epub_a4_word.cover.crop_frame import build_crop_frame
from epub_a4_word.cover.geometry import RectMm, calculate_layout
from epub_a4_word.cover.models import LogoAssetMetadata, Region
from epub_a4_word.cover.render import mm_to_px, render_spread
from epub_a4_word.cover.templates import apply_template


ACCENT = (223, 107, 50)


def _inside(transform, rect: RectMm) -> bool:
    return (
        transform.x_mm >= rect.x_mm
        and transform.y_mm >= rect.y_mm
        and transform.x_mm + transform.width_mm <= rect.right_mm + 1e-9
        and transform.y_mm + transform.height_mm <= rect.bottom_mm + 1e-9
    )


def _element_crop(image: Image.Image, element, dpi: int) -> Image.Image:
    transform = element.transform
    return image.crop(
        (
            mm_to_px(transform.x_mm, dpi),
            mm_to_px(transform.y_mm, dpi),
            mm_to_px(transform.x_mm + transform.width_mm, dpi),
            mm_to_px(transform.y_mm + transform.height_mm, dpi),
        )
    )


def _reference_project(sample_project, tmp_path):
    logo_path = tmp_path / "publisher-logo.png"
    logo = Image.new("RGBA", (240, 120), (255, 255, 255, 0))
    for x in range(35, 205):
        for y in range(25, 95):
            if (x - 120) ** 2 / 85**2 + (y - 60) ** 2 / 36**2 <= 1:
                logo.putpixel((x, y), (*ACCENT, 255))
    logo.save(logo_path)

    base = sample_project(manual_spine_width_mm=12.0)
    metadata = replace(
        base.metadata,
        title="歡迎來到實力至上主義的教室",
        english_title="Welcome to the Classroom of the Elite",
        author="衣笠彰梧",
        isbn="9786263211094",
        publisher="台灣角川",
        price="NT$240/HK$80",
        translator="Arieru",
        arc_label="二年級篇",
        volume_number="3",
        internal_book_code="CL0308-17",
        back_vertical_copy=(
            "以四季如夏的無人島為舞台，全年級互相競爭來獲得分數的野外求生考試終於開始了。\n"
            "學生必須依照指定條件完成課題，並面對無人島上的各種考驗。"
        ),
        back_highlight_copy="「被雍町上的話……可能會很不妙。」\n綾小路同學，你最好趁現在跟人多一點的小組——",
        spine_style="reference_stacked",
        spine_accent_color="#DF6B32",
        accent_color_mode="manual",
        publisher_logo=LogoAssetMetadata(
            asset_id="reference-logo",
            path=str(logo_path),
            image_format="png",
            width_px=240,
            height_px=120,
            manual_selection=True,
        ),
    )
    return apply_template(
        replace(base, metadata=metadata),
        "modern_vertical_back_with_spine",
    )


def test_reference_layout_keeps_everything_in_its_print_region(
    sample_project, tmp_path
) -> None:
    project = _reference_project(sample_project, tmp_path)
    layout = calculate_layout(project)

    back_elements = [
        element for element in project.elements if element.region is Region.BACK
    ]
    spine_elements = [
        element
        for element in project.elements
        if element.id.startswith("modern-spine-")
    ]

    assert back_elements
    assert spine_elements
    assert all(_inside(element.transform, layout.back_safe_rect) for element in back_elements)
    assert all(_inside(element.transform, layout.spine_rect) for element in spine_elements)
    assert not any(
        element.id.startswith("modern-back-bottom-decoration")
        for element in project.elements
    )
    assert project.elements_by_id["back-isbn-code"].transform.y_mm < project.elements_by_id[
        "modern-back-copy-column-1"
    ].transform.y_mm

    lines = build_crop_frame(project, layout)
    assert {(line.x1_mm, line.y1_mm, line.x2_mm, line.y2_mm) for line in lines} == {
        (layout.spread_rect.x_mm, layout.spread_rect.y_mm, layout.spread_rect.right_mm, layout.spread_rect.y_mm),
        (layout.spread_rect.right_mm, layout.spread_rect.y_mm, layout.spread_rect.right_mm, layout.spread_rect.bottom_mm),
        (layout.spread_rect.right_mm, layout.spread_rect.bottom_mm, layout.spread_rect.x_mm, layout.spread_rect.bottom_mm),
        (layout.spread_rect.x_mm, layout.spread_rect.bottom_mm, layout.spread_rect.x_mm, layout.spread_rect.y_mm),
    }


def test_reference_render_has_vertical_copy_accent_badge_and_blank_bottom(
    sample_project, tmp_path
) -> None:
    dpi = 200
    project = _reference_project(sample_project, tmp_path)
    layout = calculate_layout(project)
    image = render_spread(project, dpi).convert("RGB")

    body = _element_crop(
        image, project.elements_by_id["modern-back-copy-column-1"], dpi
    )
    highlight = _element_crop(
        image, project.elements_by_id["modern-back-highlight-column-1"], dpi
    )
    badge = _element_crop(
        image, project.elements_by_id["modern-spine-volume-badge"], dpi
    )
    assert any(max(pixel) < 160 for pixel in body.getdata())
    assert any(
        sum(abs(pixel[index] - ACCENT[index]) for index in range(3)) < 75
        for pixel in highlight.getdata()
    )
    assert any(
        sum(abs(pixel[index] - ACCENT[index]) for index in range(3)) < 75
        for pixel in badge.getdata()
    )

    safe = layout.back_safe_rect
    bottom_blank = image.crop(
        (
            mm_to_px(safe.x_mm, dpi),
            mm_to_px(safe.y_mm + safe.height_mm * 0.92, dpi),
            mm_to_px(safe.right_mm, dpi),
            mm_to_px(safe.y_mm + safe.height_mm * 0.98, dpi),
        )
    )
    assert all(min(pixel) >= 248 for pixel in bottom_blank.getdata())

    frame = layout.spread_rect
    mid_x = mm_to_px(frame.x_mm + frame.width_mm / 2, dpi)
    mid_y = mm_to_px(frame.y_mm + frame.height_mm / 2, dpi)
    left = mm_to_px(frame.x_mm, dpi)
    right = mm_to_px(frame.right_mm, dpi)
    top = mm_to_px(frame.y_mm, dpi)
    bottom = mm_to_px(frame.bottom_mm, dpi)
    assert max(image.getpixel((mid_x, top))) < 20
    assert max(image.getpixel((mid_x, bottom))) < 20
    assert max(image.getpixel((left, mid_y))) < 20
    assert max(image.getpixel((right, mid_y))) < 20
