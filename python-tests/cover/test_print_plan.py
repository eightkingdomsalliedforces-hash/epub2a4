from __future__ import annotations

from typing import Callable

import pytest

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import CoverProject
from epub_a4_word.cover.print_plan import build_print_plan


def test_a6_spread_fits_one_landscape_a4(
    sample_project: Callable[..., CoverProject],
) -> None:
    plan = build_print_plan(calculate_layout(sample_project(trim=(105.0, 148.0))))
    assert plan.mode == "single"
    assert len(plan.pages) == 1
    assert plan.pages[0].orientation == "landscape"
    assert plan.pages[0].paper_size_mm == (297.0, 210.0)
    assert plan.pages[0].scale == 1.0


def test_a5_spread_splits_without_scaling(
    sample_project: Callable[..., CoverProject],
) -> None:
    plan = build_print_plan(calculate_layout(sample_project(trim=(148.0, 210.0))))
    assert plan.mode == "split"
    assert [page.name for page in plan.pages] == ["back", "spine", "front"]
    assert all(page.scale == 1.0 for page in plan.pages)
    assert plan.pages[0].source_rect.width_mm == pytest.approx(148.0 + 3.0 + 5.0)
    assert plan.pages[1].left_overlap_mm == pytest.approx(5.0)
    assert plan.pages[1].right_overlap_mm == pytest.approx(5.0)
    assert plan.pages[2].source_rect.width_mm == pytest.approx(5.0 + 148.0 + 3.0)


def test_every_tile_is_centered_on_exact_a4_and_has_marks(
    sample_project: Callable[..., CoverProject],
) -> None:
    plan = build_print_plan(calculate_layout(sample_project(trim=(148.0, 210.0))))
    for page in plan.pages:
        paper_w, paper_h = page.paper_size_mm
        assert page.destination_rect.x_mm == pytest.approx(
            (paper_w - page.source_rect.width_mm) / 2
        )
        assert page.destination_rect.y_mm == pytest.approx(
            (paper_h - page.source_rect.height_mm) / 2
        )
        assert page.destination_rect.width_mm == pytest.approx(page.source_rect.width_mm)
        assert page.destination_rect.height_mm == pytest.approx(page.source_rect.height_mm)
        assert page.marks
