from __future__ import annotations

import pytest

from epub_a4_word.page_placement import CropGuide, build_page_placement
from epub_a4_word.pagination import LayoutSettings, resolve_layout


def _resolved(mode: str, **kwargs):
    return resolve_layout(LayoutSettings(imposition_mode=mode, **kwargs))


def test_b6_on_a5_uses_bottom_right_trim_and_full_cut_lines() -> None:
    placement = build_page_placement(
        _resolved("b6_on_a5", output_mark_mode="crop_marks")
    )

    assert (
        placement.paper_width_mm,
        placement.paper_height_mm,
    ) == pytest.approx((148.0, 210.0))
    assert (
        placement.content_x_mm,
        placement.content_y_mm,
        placement.content_width_mm,
        placement.content_height_mm,
    ) == pytest.approx((20.0, 28.0, 128.0, 182.0))
    assert placement.guides == (
        CropGuide(0.0, 28.0, 148.0, 28.0, "crop"),
        CropGuide(20.0, 0.0, 20.0, 210.0, "crop"),
    )


def test_b6_normal_mode_keeps_bottom_right_placement_without_guides() -> None:
    placement = build_page_placement(
        _resolved("b6_on_a5", output_mark_mode="normal")
    )
    assert (placement.content_x_mm, placement.content_y_mm) == pytest.approx(
        (20.0, 28.0)
    )
    assert placement.guides == ()


@pytest.mark.parametrize("mode", ["single_a5", "single_4x6"])
def test_single_sheet_modes_have_no_internal_guides(mode: str) -> None:
    placement = build_page_placement(
        _resolved(mode, output_mark_mode="crop_marks")
    )
    assert placement.guides == ()


def test_four_up_uses_one_solid_vertical_and_horizontal_crop_guide() -> None:
    placement = build_page_placement(_resolved("four_up", cut_guides=True))
    assert placement.guides == (
        CropGuide(105.0, 7.0, 105.0, 295.0, "crop"),
        CropGuide(2.0, 151.0, 208.0, 151.0, "crop"),
    )


def test_signature16_uses_fold_guides() -> None:
    placement = build_page_placement(_resolved("signature16", cut_guides=True))
    assert placement.guides == (
        CropGuide(105.0, 7.0, 105.0, 295.0, "fold"),
        CropGuide(2.0, 151.0, 208.0, 151.0, "fold"),
    )


def test_grid_guides_can_be_disabled() -> None:
    assert build_page_placement(
        _resolved("four_up", cut_guides=False)
    ).guides == ()
    assert build_page_placement(
        _resolved("signature16", cut_guides=False)
    ).guides == ()
