from __future__ import annotations

from epub_a4_word.cover.geometry import RectMm
from epub_a4_word.cover.vertical_copy_layout import layout_vertical_copy


def test_vertical_copy_runs_right_to_left_without_overflow() -> None:
    target = RectMm(20, 40, 82, 110)

    result = layout_vertical_copy(
        "第一欄文字。\n第二欄文字。\n第三欄文字。",
        target,
        preferred_font_pt=10.0,
        minimum_font_pt=7.0,
        preferred_gap_mm=2.0,
        maximum_columns=10,
    )

    assert len(result.columns) == 3
    assert all(
        target.x_mm <= column.rect.x_mm
        and column.rect.right_mm <= target.right_mm
        and target.y_mm <= column.rect.y_mm
        and column.rect.bottom_mm <= target.bottom_mm
        for column in result.columns
    )
    assert [column.rect.x_mm for column in result.columns] == sorted(
        (column.rect.x_mm for column in result.columns),
        reverse=True,
    )
    assert result.warnings == ()


def test_vertical_copy_warns_instead_of_truncating() -> None:
    text = "字" * 1000

    result = layout_vertical_copy(
        text,
        RectMm(0, 0, 30, 40),
        preferred_font_pt=10,
        minimum_font_pt=7,
        preferred_gap_mm=1,
        maximum_columns=4,
    )

    assert "".join(column.text for column in result.columns) == text
    assert len(result.columns) == 4
    assert result.warnings == ("封底直排內文超出可用範圍。",)
