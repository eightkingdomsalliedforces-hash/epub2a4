from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from epub_a4_word_desktop.conversion.models import ConversionCompletion
from epub_a4_word_desktop.pages.converter_page import ConverterPage


class FakeController(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.started = []
        self.cancel_count = 0
        self.is_running = False

    def start(self, request) -> None:
        self.started.append(request)
        self.is_running = True

    def cancel(self) -> None:
        self.cancel_count += 1


def completion(source: Path, output: Path) -> ConversionCompletion:
    return ConversionCompletion(
        source=source,
        output_path=output,
        actual_page_count=64,
        trim_size_mm=(105.0, 148.0),
        title="書名",
        author="作者",
        warnings=("警告一", "警告二"),
        imposition_mode="signature16",
    )


def test_docx_source_limits_available_modes(qtbot, tmp_path: Path) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)
    source = tmp_path / "book.docx"
    source.write_bytes(b"docx")

    page.set_source_path(source)

    assert [page.mode_combo.itemData(index) for index in range(page.mode_combo.count())] == [
        "single_a5",
        "single_4x6",
    ]
    assert Path(page.output_edit.text()).suffix.lower() == ".docx"


def test_start_builds_request_from_form(qtbot, tmp_path: Path) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    page.set_source_path(source)
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("four_up"))
    page.margin_combo.setCurrentIndex(page.margin_combo.findData("borderless"))
    page.body_size.setValue(10.5)
    page.heading_size.setValue(16.0)
    page.page_numbers.setChecked(False)
    page.cut_guides.setChecked(True)

    page._start_conversion()

    request = controller.started[-1]
    assert request.input_path == source
    assert request.imposition_mode == "four_up"
    assert request.margin_mode == "borderless"
    assert request.body_font_pt == 10.5
    assert request.heading_font_pt == 16.0
    assert request.page_numbers is False
    assert request.cut_guides is True
    assert request.writing_mode == "taiwan_vertical"
    assert request.binding_direction == "right"
    assert page.start_button.isEnabled() is False
    assert page.cancel_button.isEnabled() is True


def test_direction_selector_builds_horizontal_left_request(
    qtbot,
    tmp_path: Path,
) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    page.set_source_path(source)

    page.direction_combo.setCurrentIndex(
        page.direction_combo.findText("橫排（左裝訂）")
    )
    page._start_conversion()

    request = controller.started[-1]
    assert request.writing_mode == "horizontal"
    assert request.binding_direction == "left"


def test_completion_shows_warnings_and_emits_cover_payload(qtbot, tmp_path: Path) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)
    source = tmp_path / "book.epub"
    output = tmp_path / "book.docx"
    result = completion(source, output)

    with patch.object(QMessageBox, "information") as information:
        controller.completed.emit(result)

    assert page.progress.value() == 100
    assert page.status_label.text() == "轉換完成。"
    assert page.warnings.toPlainText() == "警告一\n警告二"
    assert page.cover_button.isVisible() is False  # parent page has not been shown yet
    assert page.cover_button.isHidden() is False
    information.assert_called_once()

    with qtbot.waitSignal(page.open_cover_requested) as signal:
        page._emit_cover_payload()
    assert signal.args[0]["source_path"] == str(source)
    assert signal.args[0]["page_count"] == 64
    assert signal.args[0]["trim_size_mm"] == {"width_mm": 105.0, "height_mm": 148.0}


def test_progress_failure_and_cancel_update_page_state(qtbot) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)

    controller.progress.emit(45, "正在排版…")
    assert page.progress.value() == 45
    assert "正在排版" in page.status_label.text()

    controller.failed.emit("壞掉了")
    assert page.status_label.text() == "轉換失敗。"
    assert "壞掉了" in page.warnings.toPlainText()
    assert page.start_button.isEnabled() is True

    page._set_running(True)
    controller.cancelled.emit()
    assert page.status_label.text() == "轉換已取消。"
    assert page.start_button.isEnabled() is True


def test_body_only_option_defaults_checked_and_tracks_source_type(qtbot, tmp_path: Path) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)

    assert page.content_only.isChecked() is True
    assert "正文插圖" in page.content_only.toolTip()

    epub = tmp_path / "book.epub"
    epub.write_bytes(b"epub")
    page.set_source_path(epub)
    assert page.content_only.isEnabled() is True

    docx = tmp_path / "book.docx"
    docx.write_bytes(b"docx")
    page.set_source_path(docx)
    assert page.content_only.isEnabled() is False
    assert "DOCX" in page.content_only.toolTip()


def test_body_only_option_is_included_in_conversion_request(qtbot, tmp_path: Path) -> None:
    controller = FakeController()
    page = ConverterPage(controller)
    qtbot.addWidget(page)
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    page.set_source_path(source)
    page.content_only.setChecked(False)

    page._start_conversion()

    assert controller.started[-1].content_only is False
