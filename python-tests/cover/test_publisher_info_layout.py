from __future__ import annotations

from pathlib import Path

import pytest

from epub_a4_word.cover import fonts
from epub_a4_word.cover.models import CoverMetadata
from epub_a4_word.cover.publisher_info_layout import (
    TextMeasure,
    build_publisher_info_lines,
    layout_publisher_info,
)
from epub_a4_word.cover.typography import font_candidates


def _fixed_measure(text: str, role: str, font_size_pt: float) -> TextMeasure:
    width_factor = 0.22 if role == "heading" else 0.19
    return TextMeasure(
        width_mm=len(text) * font_size_pt * width_factor,
        line_height_mm=font_size_pt * 0.35,
    )


def test_publisher_lines_skip_empty_values_and_do_not_duplicate_translator_prefix() -> None:
    metadata = CoverMetadata(
        publisher=" 台灣角川 ",
        price=" NT$110/HK$35 ",
        publication_place="   ",
        translator="譯者：李彥樺",
    )

    lines = build_publisher_info_lines(metadata)

    assert [(line.role, line.text) for line in lines] == [
        ("heading", "台灣角川"),
        ("details", "定價：NT$110/HK$35"),
        ("details", "譯者：李彥樺"),
    ]


def test_missing_heading_starts_details_at_stack_top() -> None:
    layout = layout_publisher_info(
        metadata=CoverMetadata(price="NT$110"),
        x_mm=80.0,
        y_mm=10.0,
        max_width_mm=50.0,
        max_height_mm=30.0,
        measure=_fixed_measure,
    )

    assert layout.heading_rect is None
    assert layout.details_rect is not None
    assert layout.details_rect.y_mm == pytest.approx(10.0)


def test_missing_middle_line_compacts_following_lines() -> None:
    layout = layout_publisher_info(
        metadata=CoverMetadata(publisher="台灣角川", translator="李彥樺"),
        x_mm=80.0,
        y_mm=10.0,
        max_width_mm=50.0,
        max_height_mm=30.0,
        measure=_fixed_measure,
    )

    assert layout.heading_rect is not None
    assert layout.details_rect is not None
    assert layout.detail_lines == ("譯者：李彥樺",)
    assert layout.details_rect.y_mm == pytest.approx(
        layout.heading_rect.bottom_mm + 1.0
    )


def test_heading_only_uses_no_fixed_details_space() -> None:
    layout = layout_publisher_info(
        metadata=CoverMetadata(publisher="台灣角川"),
        x_mm=80.0,
        y_mm=10.0,
        max_width_mm=50.0,
        max_height_mm=30.0,
        measure=_fixed_measure,
    )

    assert layout.heading_rect is not None
    assert layout.details_rect is None
    assert layout.height_mm == pytest.approx(layout.heading_rect.height_mm)


def test_dfp_yuan_gb_names_are_first_candidates() -> None:
    assert font_candidates("publisher_heading")[:4] == (
        "DFPYuanW5-GB",
        "DFPYuanW5",
        "DFP Yuan W5",
        "DFYuan-W5",
    )
    assert font_candidates("publisher_details")[:4] == (
        "DFPYuanW3-GB",
        "DFPYuanW3",
        "DFP Yuan W3",
        "DFYuan-W3",
    )


def test_font_matching_supports_declared_alias_without_substring_guessing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intended = tmp_path / "DFPYuanW5-GB.ttf"
    unrelated = tmp_path / "MyDFPYuanW5Backup.ttf"
    intended.touch()
    unrelated.touch()
    monkeypatch.setattr(fonts, "_installed_font_files", lambda: (unrelated, intended))

    assert fonts._matching_font_path(("DFP Yuan W5",)) == intended
    assert fonts._matching_font_path(("DFPYuanW4",)) is None


def test_font_matching_ignores_only_known_style_suffixes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intended = tmp_path / "NotoSansCJK-Regular.ttc"
    unrelated = tmp_path / "MyNotoSansCJKBackup.ttc"
    intended.touch()
    unrelated.touch()
    monkeypatch.setattr(fonts, "_installed_font_files", lambda: (unrelated, intended))

    assert fonts._matching_font_path(("Noto Sans CJK TC",)) == intended
