from __future__ import annotations

from dataclasses import replace

import pytest

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.modern_spine_layout import build_modern_spine_slots


@pytest.mark.parametrize(
    ("style", "expected_roles"),
    [
        (
            "reference_stacked",
            {
                "logo",
                "english_title",
                "title",
                "arc",
                "volume_badge",
                "author",
                "code",
                "publisher",
            },
        ),
        (
            "clean_centered",
            {"logo", "title", "arc", "volume_badge", "author", "publisher"},
        ),
        (
            "parallel_columns",
            {
                "logo",
                "english_title",
                "title",
                "arc",
                "volume_badge",
                "author",
                "code",
                "publisher",
            },
        ),
    ],
)
def test_spine_style_roles(style, expected_roles, sample_project) -> None:
    project = replace(
        sample_project(manual_spine_width_mm=8.0),
        metadata=replace(sample_project().metadata, spine_style=style),
    )

    result = build_modern_spine_slots(
        calculate_layout(project),
        style,
        "#DF6B32",
    )

    assert {slot.role for slot in result.slots} == expected_roles


@pytest.mark.parametrize("width", [4.0, 6.03, 8.0, 12.0])
@pytest.mark.parametrize(
    "style",
    ["reference_stacked", "clean_centered", "parallel_columns"],
)
def test_all_spine_slots_stay_inside_real_spine(
    width, style, sample_project
) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=width))

    result = build_modern_spine_slots(layout, style, "#DF6B32")

    assert all(
        layout.spine_rect.x_mm <= slot.rect.x_mm
        and slot.rect.right_mm <= layout.spine_rect.right_mm
        and layout.spine_rect.y_mm <= slot.rect.y_mm
        and slot.rect.bottom_mm <= layout.spine_rect.bottom_mm
        for slot in result.slots
    )


def test_unknown_spine_style_falls_back_with_warning(sample_project) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=8.0))

    result = build_modern_spine_slots(layout, "unknown", "#DF6B32")

    assert result.style == "reference_stacked"
    assert result.warnings == ("未知書脊樣式，已改用參考圖堆疊式。",)
