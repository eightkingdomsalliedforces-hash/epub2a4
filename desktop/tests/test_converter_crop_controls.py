from __future__ import annotations

from pathlib import Path

from epub_a4_word_desktop.pages.converter_page import ConverterPage


def test_b6_uses_same_crop_checkbox_and_builds_crop_mark_request(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"fixture")
    page = ConverterPage()
    qtbot.addWidget(page)
    page.set_source_path(source)
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("b6_on_a5"))
    page.cut_guides.setChecked(True)

    request = page._build_request()

    assert page.cut_guides.isEnabled()
    assert request.cut_guides is True
    assert request.output_mark_mode == "crop_marks"


def test_high_compatibility_checkbox_selects_drawingml(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"fixture")
    page = ConverterPage()
    qtbot.addWidget(page)
    page.set_source_path(source)
    page.high_compat_guides.setChecked(True)

    request = page._build_request()

    assert request.guide_render_mode == "drawingml"
