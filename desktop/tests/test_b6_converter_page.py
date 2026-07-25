from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from epub_a4_word_desktop.pages.converter_page import ConverterPage


class FakeController(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def start(self, request) -> None:
        del request

    def cancel(self) -> None:
        pass


def test_b6_mode_shows_mark_choice_and_builds_request(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"placeholder")
    page = ConverterPage(FakeController())
    qtbot.addWidget(page)
    page.show()

    page.set_source_path(source)
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("b6_on_a5"))

    assert page.output_mark_combo.isVisible()
    assert page.layout_preview.isVisible()
    assert page.cut_guides.isVisible() is False
    assert page.output_mark_combo.currentData() == "normal"

    page.output_mark_combo.setCurrentIndex(
        page.output_mark_combo.findData("crop_marks")
    )
    request = page._build_request()

    assert request.imposition_mode == "b6_on_a5"
    assert request.output_mark_mode == "crop_marks"
    assert page.layout_preview.mark_mode == "crop_marks"

    page.mode_combo.setCurrentIndex(page.mode_combo.findData("four_up"))
    assert page.output_mark_combo.isVisible() is False
    assert page.layout_preview.isVisible() is False
    assert page.cut_guides.isVisible()
    assert page._build_request().output_mark_mode == "normal"
