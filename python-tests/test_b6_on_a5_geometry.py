import pytest

from epub_a4_word.pagination import LayoutSettings, resolve_layout


def test_b6_on_a5_geometry_is_centered_and_uses_internal_book_margins() -> None:
    resolved = resolve_layout(
        LayoutSettings(imposition_mode="b6_on_a5", margin_mode="safe")
    )

    assert resolved.paper_width_cm == pytest.approx(14.8)
    assert resolved.paper_height_cm == pytest.approx(21.0)
    assert resolved.page_margin_left_cm == pytest.approx(1.0)
    assert resolved.page_margin_right_cm == pytest.approx(1.0)
    assert resolved.page_margin_top_cm == pytest.approx(1.4)
    assert resolved.page_margin_bottom_cm == pytest.approx(1.4)
    assert resolved.cell_width_cm == pytest.approx(12.8)
    assert resolved.cell_height_cm == pytest.approx(18.2)
    assert resolved.grid_rows == 1
    assert resolved.grid_cols == 1
    assert resolved.page_prefix_height_cm == pytest.approx(0.0)
    assert resolved.content_width_pt < 12.8 * 72 / 2.54
    assert resolved.content_height_pt < 18.2 * 72 / 2.54


def test_existing_single_a5_geometry_keeps_symmetric_page_margins() -> None:
    resolved = resolve_layout(
        LayoutSettings(imposition_mode="single_a5", margin_mode="safe")
    )

    assert resolved.page_margin_left_cm == pytest.approx(resolved.outer_margin_cm)
    assert resolved.page_margin_right_cm == pytest.approx(resolved.outer_margin_cm)
    assert resolved.page_margin_top_cm == pytest.approx(resolved.outer_margin_cm)
    assert resolved.page_margin_bottom_cm == pytest.approx(resolved.outer_margin_cm)
