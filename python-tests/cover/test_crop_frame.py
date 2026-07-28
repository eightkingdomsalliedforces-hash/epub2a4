from __future__ import annotations

from dataclasses import replace

from epub_a4_word.cover.crop_frame import build_crop_frame
from epub_a4_word.cover.geometry import calculate_layout


def test_crop_frame_is_exactly_spread_rect(sample_project) -> None:
    project = sample_project()
    layout = calculate_layout(project)

    lines = build_crop_frame(project, layout)

    assert {
        (line.x1_mm, line.y1_mm, line.x2_mm, line.y2_mm)
        for line in lines
    } == {
        (
            layout.spread_rect.x_mm,
            layout.spread_rect.y_mm,
            layout.spread_rect.right_mm,
            layout.spread_rect.y_mm,
        ),
        (
            layout.spread_rect.right_mm,
            layout.spread_rect.y_mm,
            layout.spread_rect.right_mm,
            layout.spread_rect.bottom_mm,
        ),
        (
            layout.spread_rect.right_mm,
            layout.spread_rect.bottom_mm,
            layout.spread_rect.x_mm,
            layout.spread_rect.bottom_mm,
        ),
        (
            layout.spread_rect.x_mm,
            layout.spread_rect.bottom_mm,
            layout.spread_rect.x_mm,
            layout.spread_rect.y_mm,
        ),
    }
    assert all(line.width_pt == 0.35 for line in lines)


def test_crop_frame_switch_off_returns_no_lines(sample_project) -> None:
    project = sample_project()
    project = replace(
        project,
        export_settings=replace(
            project.export_settings,
            show_crop_marks=False,
        ),
    )

    assert build_crop_frame(project, calculate_layout(project)) == ()
