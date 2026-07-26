from __future__ import annotations

from dataclasses import replace

import pytest

from epub_a4_word.cover.barcode_layout import build_barcode_layout
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import CoverMetadata, CoverProject, ImageMode, TrimSize
from epub_a4_word.cover.templates import apply_template
from epub_a4_word.cover.typography import font_candidates, points_to_mm


def _project() -> CoverProject:
    return CoverProject(
        schema_version=1,
        source_file="book.epub",
        source_type="epub",
        metadata=CoverMetadata(
            title="魔法禁書目錄 1",
            author="鎌池和馬",
            publisher="台灣角川",
            isbn="9789862370773",
            isbn_addon="00110",
            price="定價：NT$110/HK$35",
            publication_place="香港代理：角川洲立出版",
        ),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=".",
    )


def test_points_are_converted_to_scene_millimetres() -> None:
    assert points_to_mm(24.0) == pytest.approx(8.4666667)
    assert points_to_mm(7.5) == pytest.approx(2.6458333)


def test_font_roles_prioritize_round_dyna_and_ocr_families() -> None:
    assert font_candidates("publisher_heading")[:2] == (
        "DFYuan-W5",
        "華康圓體 Std W5",
    )
    assert font_candidates("publisher_details")[:2] == (
        "DFYuan-W3",
        "華康圓體 Std W3",
    )
    assert font_candidates("ocr")[:4] == (
        "OCR-B",
        "OCR B Std",
        "OCRB",
        "OCR-B 10 BT",
    )


def test_publisher_template_separates_round_heading_and_details() -> None:
    result = apply_template(_project(), "publisher_back_matter")
    ids = result.elements_by_id

    assert "back-publisher-info" not in ids
    assert ids["back-isbn-label"].content["font_role"] == "ocr"
    assert ids["back-isbn-label"].content["font_size_pt"] == pytest.approx(7.0)
    assert ids["back-publisher-heading"].content["text"] == "台灣角川"
    assert ids["back-publisher-heading"].content["font_role"] == "publisher_heading"
    assert ids["back-publisher-heading"].content["font_size_pt"] == pytest.approx(7.5)
    assert ids["back-publisher-details"].content["font_role"] == "publisher_details"
    assert ids["back-publisher-details"].content["font_size_pt"] == pytest.approx(6.5)
    assert ids["back-publisher-details"].content["text"] == (
        "定價：NT$110/HK$35\n香港代理：角川洲立出版"
    )

    safe = calculate_layout(result).back_safe_rect
    heading = ids["back-publisher-heading"].transform
    details = ids["back-publisher-details"].transform
    barcode = ids["back-isbn-code"].transform
    assert heading.x_mm > barcode.x_mm
    assert details.x_mm == pytest.approx(heading.x_mm)
    assert details.y_mm > heading.y_mm
    assert heading.x_mm + heading.width_mm <= safe.right_mm
    assert details.x_mm + details.width_mm <= safe.right_mm


def test_barcode_layout_places_reference_digits_and_addon() -> None:
    layout = build_barcode_layout("9789862370773", "00110")

    assert layout.first_digit.text == "9"
    assert layout.left_digits.text == "789862"
    assert layout.right_digits.text == "370773"
    assert layout.addon_digits is not None
    assert layout.addon_digits.text == "00110"
    assert layout.addon_digits.bottom <= min(bar.top for bar in layout.addon_bars)
    assert max(bar.bottom for bar in layout.guard_bars) > max(
        bar.bottom for bar in layout.data_bars
    )
