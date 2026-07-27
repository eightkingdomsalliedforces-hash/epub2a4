from __future__ import annotations

from typing import Callable

import pytest

from epub_a4_word.cover.geometry import CoverLayoutError, calculate_layout
from epub_a4_word.cover.models import CoverProject


def test_spine_uses_sheet_count_and_caliper(
    sample_project: Callable[..., CoverProject],
) -> None:
    layout = calculate_layout(sample_project(page_count=161, paper_caliper_mm=0.10))
    assert layout.sheet_count == 81
    assert layout.spine_width_mm == pytest.approx(8.1)


def test_manual_spine_override_wins(sample_project: Callable[..., CoverProject]) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=9.4))
    assert layout.spine_width_mm == pytest.approx(9.4)


@pytest.mark.parametrize(
    ("width_mm", "expected_inset_mm"),
    [(4.0, 0.48), (6.03, 0.7236), (8.0, 0.96), (12.0, 1.0)],
)
def test_spine_safe_rect_uses_adaptive_horizontal_inset(
    sample_project: Callable[..., CoverProject],
    width_mm: float,
    expected_inset_mm: float,
) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=width_mm))

    assert layout.spine_safe_rect.x_mm == pytest.approx(
        layout.spine_rect.x_mm + expected_inset_mm
    )
    assert layout.spine_safe_rect.width_mm == pytest.approx(
        width_mm - 2.0 * expected_inset_mm
    )


def test_133_pages_at_point_09_mm_keeps_readable_spine_width(
    sample_project: Callable[..., CoverProject],
) -> None:
    layout = calculate_layout(
        sample_project(
            page_count=133,
            paper_caliper_mm=0.09,
            manual_spine_width_mm=None,
        )
    )

    assert layout.spine_width_mm == pytest.approx(6.03)
    assert layout.spine_safe_rect.width_mm == pytest.approx(4.5828)


def test_cover_order_is_back_spine_front(
    sample_project: Callable[..., CoverProject],
) -> None:
    layout = calculate_layout(sample_project(trim=(105.0, 148.0), bleed_mm=3.0))
    assert layout.back_rect.x_mm == pytest.approx(3.0)
    assert layout.spine_rect.x_mm == pytest.approx(108.0)
    assert layout.front_rect.x_mm == pytest.approx(108.0 + layout.spine_width_mm)
    assert layout.spread_rect.width_mm == pytest.approx(210.0 + layout.spine_width_mm)
    assert layout.bleed_rect.width_mm == pytest.approx(
        layout.spread_rect.width_mm + 6.0
    )


def test_safe_rectangles_stay_inside_their_regions(
    sample_project: Callable[..., CoverProject],
) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=10.0))
    assert layout.back_safe_rect.x_mm >= layout.back_rect.x_mm
    assert layout.back_safe_rect.right_mm <= layout.back_rect.right_mm
    assert layout.spine_safe_rect.x_mm >= layout.spine_rect.x_mm
    assert layout.spine_safe_rect.right_mm <= layout.spine_rect.right_mm
    assert layout.front_safe_rect.x_mm >= layout.front_rect.x_mm
    assert layout.front_safe_rect.right_mm <= layout.front_rect.right_mm


def test_invalid_project_is_reported_as_layout_error(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project(page_count=0)
    with pytest.raises(CoverLayoutError, match="page_count"):
        calculate_layout(project)
