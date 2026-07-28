from __future__ import annotations

from dataclasses import replace

import pytest

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.modern_spine_layout import (
    build_modern_spine_slots,
    fit_spine_font_size,
)


@pytest.mark.parametrize(
    ("style", "expected_roles"),
    [
        (
            "reference_stacked",
            {
                "logo",
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


@pytest.mark.parametrize(
    ("width", "tier", "roles"),
    [
        (
            12.0,
            "full",
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
            8.0,
            "compact",
            {
                "logo",
                "title",
                "arc",
                "volume_badge",
                "author",
                "code",
                "publisher",
            },
        ),
        (
            4.0,
            "minimal",
            {
                "logo",
                "title",
                "arc",
                "volume_badge",
                "author",
                "publisher",
            },
        ),
    ],
)
def test_reference_spine_degrades_by_width(width, tier, roles, sample_project) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=width)),
        "reference_stacked",
        "#DF6B32",
    )

    assert result.tier == tier
    assert {slot.role for slot in result.slots} == roles


def test_reference_spine_title_is_dominant_and_publisher_is_last(
    sample_project,
) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=12.0))
    result = build_modern_spine_slots(layout, "reference_stacked", "#DF6B32")
    slots = {slot.role: slot for slot in result.slots}

    assert slots["title"].font_size_pt > slots["author"].font_size_pt
    assert slots["title"].font_size_pt > slots["publisher"].font_size_pt
    assert slots["logo"].rect.bottom_mm <= slots["english_title"].rect.y_mm
    assert slots["publisher"].rect.bottom_mm <= layout.spine_rect.bottom_mm


def test_long_reference_title_fits_without_dropping_below_readable_minimum(
    sample_project,
) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=8.0)),
        "reference_stacked",
        "#DF6B32",
    )
    title = next(slot for slot in result.slots if slot.role == "title")

    fitted, warnings = fit_spine_font_size(
        title,
        "歡迎來到實力至上主義的教室二年級篇",
    )

    assert fitted >= 6.0
    assert fitted <= title.font_size_pt
    assert isinstance(warnings, tuple)


@pytest.mark.parametrize("width", [4.0, 6.03, 8.0, 12.0])
def test_reference_full_width_slots_do_not_overlap(width, sample_project) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=width)),
        "reference_stacked",
        "#DF6B32",
    )
    full_width = [
        slot
        for slot in result.slots
        if slot.rect.width_mm
        == pytest.approx(calculate_layout(
            sample_project(manual_spine_width_mm=width)
        ).spine_safe_rect.width_mm)
    ]

    for first, second in zip(full_width, full_width[1:]):
        assert first.rect.bottom_mm <= second.rect.y_mm


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
