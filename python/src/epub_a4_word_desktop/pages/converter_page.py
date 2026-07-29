from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..conversion.controller import ConversionController
from ..conversion.layout_preview import LayoutPreview
from ..conversion.legacy_adapter import allowed_modes_for_path
from ..conversion.models import ConversionCompletion, ConversionRequest

_MODE_LABELS = {
    "signature16": "A6 書帖（16 頁一組）",
    "four_up": "A4 四格 A6",
    "single_a5": "A5 單頁",
    "single_4x6": "4×6 英吋單頁",
    "b6_on_a5": "B6 內容置於 A5 紙張",
}
_MARGIN_LABELS = {
    "safe": "安全邊界",
    "maximized": "最大化內容",
    "borderless": "無外邊界",
}
_DIRECTION_PRESETS = (
    ("台灣直排（右裝訂）", ("taiwan_vertical", "right")),
    ("橫排（左裝訂）", ("horizontal", "left")),
)


class ConverterPage(QWidget):
    back_requested = Signal()
    open_cover_requested = Signal(dict)

    def __init__(
        self,
        controller: ConversionController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("converter-page")
        self.controller = controller or ConversionController(parent=self)
        self._completion: ConversionCompletion | None = None

        self.source_edit = QLineEdit(self)
        self.source_edit.setObjectName("conversion-source")
        self.source_button = QPushButton("選擇來源", self)
        self.source_button.clicked.connect(self._choose_source)
        self.output_edit = QLineEdit(self)
        self.output_edit.setObjectName("conversion-output")
        self.output_button = QPushButton("選擇輸出", self)
        self.output_button.clicked.connect(self._choose_output)

        self.mode_combo = QComboBox(self)
        self.mode_combo.setObjectName("conversion-mode")
        self.direction_combo = QComboBox(self)
        self.direction_combo.setObjectName("conversion-writing-direction")
        for label, value in _DIRECTION_PRESETS:
            self.direction_combo.addItem(label, value)
        self.margin_combo = QComboBox(self)
        for value, label in _MARGIN_LABELS.items():
            self.margin_combo.addItem(label, value)
        self.font_edit = QLineEdit("Noto Serif CJK TC", self)
        self.body_size = QDoubleSpinBox(self)
        self.body_size.setRange(6.0, 24.0)
        self.body_size.setSingleStep(0.5)
        self.body_size.setValue(9.0)
        self.heading_size = QDoubleSpinBox(self)
        self.heading_size.setRange(8.0, 36.0)
        self.heading_size.setSingleStep(0.5)
        self.heading_size.setValue(14.0)
        self.page_numbers = QCheckBox("顯示頁碼", self)
        self.page_numbers.setChecked(True)
        self.cut_guides = QCheckBox("顯示裁切／折線", self)
        self.cut_guides.setChecked(True)
        self.high_compat_guides = QCheckBox("高相容裁切線", self)
        self.high_compat_guides.setChecked(True)
        self.high_compat_guides.setToolTip(
            "改用 DrawingML 頁面圖形，供不完整支援 VML 的 Word 閱讀器使用。"
        )
        self.content_only = QCheckBox("只輸出內文，不含封面與封底", self)
        self.content_only.setObjectName("conversion-content-only")
        self.content_only.setChecked(True)
        self.content_only.setToolTip(
            "只排除已明確辨識或由你確認的 EPUB 封面頁；不會刪除正文插圖。"
        )
        self.layout_preview = LayoutPreview(self)
        self.b6_preview = self.layout_preview

        self.start_button = QPushButton("開始轉換", self)
        self.start_button.clicked.connect(self._start_conversion)
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.back_button = QPushButton("返回首頁", self)
        self.back_button.clicked.connect(lambda _checked=False: self.back_requested.emit())
        self.cover_button = QPushButton("製作獨立書封", self)
        self.cover_button.clicked.connect(self._emit_cover_payload)
        self.cover_button.hide()

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.status_label = QLabel("請選擇 EPUB 或 DOCX。", self)
        self.warnings = QPlainTextEdit(self)
        self.warnings.setReadOnly(True)
        self.warnings.setPlaceholderText("警告與轉換訊息會顯示在這裡。")

        source_row = QWidget(self)
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(self.source_button)
        output_row = QWidget(self)
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(self.output_button)

        form = QFormLayout()
        form.addRow("來源檔案", source_row)
        form.addRow("輸出 DOCX", output_row)
        form.addRow("輸出模式", self.mode_combo)
        form.addRow("正文方向", self.direction_combo)
        form.addRow("邊界模式", self.margin_combo)
        form.addRow("版面預覽", self.layout_preview)
        form.addRow("字型", self.font_edit)
        form.addRow("內文字級", self.body_size)
        form.addRow("標題字級", self.heading_size)
        form.addRow("", self.page_numbers)
        form.addRow("", self.cut_guides)
        form.addRow("", self.high_compat_guides)
        form.addRow("", self.content_only)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.back_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.cover_button)
        layout = QVBoxLayout(self)
        title = QLabel("EPUB／Word 轉換工具", self)
        title.setObjectName("converter-title")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(action_layout)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addWidget(self.warnings, 1)

        self.controller.progress.connect(self._on_progress)
        self.controller.completed.connect(self._on_completed)
        self.controller.failed.connect(self._on_failed)
        self.controller.cancelled.connect(self._on_cancelled)
        self.source_edit.editingFinished.connect(self._sync_source_from_text)
        self.mode_combo.currentIndexChanged.connect(self._sync_mode_controls)
        self.direction_combo.currentIndexChanged.connect(self._sync_mode_controls)
        self.cut_guides.toggled.connect(self._sync_mode_controls)
        self.high_compat_guides.toggled.connect(self._sync_mode_controls)
        self._populate_modes(Path("book.epub"))
        self._sync_mode_controls()
        self._set_running(False)

    def _populate_modes(self, source: Path) -> None:
        selected = self.mode_combo.currentData()
        self.mode_combo.clear()
        modes = allowed_modes_for_path(source)
        for value in modes:
            self.mode_combo.addItem(_MODE_LABELS[value], value)
        if selected in modes:
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(selected))
        is_epub = source.suffix.lower() == ".epub"
        self.content_only.setEnabled(is_epub)
        self.content_only.setToolTip(
            "只排除已明確辨識或由你確認的 EPUB 封面頁；不會刪除正文插圖。"
            if is_epub
            else "DOCX 重排不含 EPUB 封面辨識，因此此選項不適用。"
        )
        self._sync_mode_controls()

    def _sync_mode_controls(self, _value: object = None) -> None:
        mode = str(self.mode_combo.currentData() or "signature16")
        self.cut_guides.setEnabled(True)
        request = self._preview_request(mode)
        self.layout_preview.set_settings(request.to_layout_settings())

    def _preview_request(self, mode: str) -> ConversionRequest:
        writing_mode, binding_direction = self._selected_direction()
        return ConversionRequest(
            input_path=Path(self.source_edit.text().strip() or "book.epub"),
            output_path=Path(self.output_edit.text().strip() or "preview.docx"),
            imposition_mode=mode,
            writing_mode=writing_mode,
            binding_direction=binding_direction,
            margin_mode=str(self.margin_combo.currentData() or "maximized"),
            font_name=self.font_edit.text(),
            body_font_pt=self.body_size.value(),
            heading_font_pt=self.heading_size.value(),
            page_numbers=self.page_numbers.isChecked(),
            cut_guides=self.cut_guides.isChecked(),
            output_mark_mode=(
                "crop_marks"
                if mode == "b6_on_a5" and self.cut_guides.isChecked()
                else "normal"
            ),
            guide_render_mode=(
                "drawingml" if self.high_compat_guides.isChecked() else "vml"
            ),
            content_only=self.content_only.isChecked(),
        )

    def _selected_direction(self) -> tuple[str, str]:
        value = self.direction_combo.currentData()
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return str(value[0]), str(value[1])
        return "taiwan_vertical", "right"

    def set_source_path(self, source: Path | str) -> None:
        path = Path(source).expanduser()
        self.source_edit.setText(str(path))
        self._populate_modes(path)
        self.output_edit.setText(str(path.with_name(f"{path.stem}.converted.docx")))
        self.status_label.setText("來源檔案已選擇。")

    @Slot()
    def _sync_source_from_text(self) -> None:
        text = self.source_edit.text().strip()
        if text:
            self._populate_modes(Path(text).expanduser())

    @Slot()
    def _choose_source(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self, "選擇 EPUB 或 DOCX", "", "EPUB／Word (*.epub *.docx)"
        )
        if value:
            self.set_source_path(value)

    @Slot()
    def _choose_output(self) -> None:
        value, _ = QFileDialog.getSaveFileName(
            self, "選擇輸出 DOCX", self.output_edit.text(), "Word 文件 (*.docx)"
        )
        if value:
            path = Path(value)
            if path.suffix.lower() != ".docx":
                path = path.with_suffix(".docx")
            self.output_edit.setText(str(path))

    def _build_request(self) -> ConversionRequest:
        mode = str(self.mode_combo.currentData() or "")
        writing_mode, binding_direction = self._selected_direction()
        return ConversionRequest(
            input_path=Path(self.source_edit.text().strip()).expanduser(),
            output_path=Path(self.output_edit.text().strip()).expanduser(),
            imposition_mode=mode,
            writing_mode=writing_mode,
            binding_direction=binding_direction,
            margin_mode=str(self.margin_combo.currentData() or ""),
            font_name=self.font_edit.text(),
            body_font_pt=self.body_size.value(),
            heading_font_pt=self.heading_size.value(),
            page_numbers=self.page_numbers.isChecked(),
            cut_guides=self.cut_guides.isChecked(),
            output_mark_mode=(
                "crop_marks"
                if mode == "b6_on_a5" and self.cut_guides.isChecked()
                else "normal"
            ),
            guide_render_mode=(
                "drawingml" if self.high_compat_guides.isChecked() else "vml"
            ),
            content_only=self.content_only.isChecked(),
        )

    @Slot()
    def _start_conversion(self) -> None:
        try:
            request = self._build_request()
            request.validate()
            self._completion = None
            self.cover_button.hide()
            self.progress.setValue(0)
            self.warnings.clear()
            self.status_label.setText("正在準備轉換…")
            self._set_running(True)
            self.controller.start(request)
        except Exception as exc:
            self._set_running(False)
            self.status_label.setText("無法開始轉換。")
            self.warnings.setPlainText(str(exc))
            QMessageBox.warning(self, "無法開始", str(exc))

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.source_button.setEnabled(not running)
        self.output_button.setEnabled(not running)
        self.direction_combo.setEnabled(not running)
        if self.source_edit.text().strip().lower().endswith(".epub"):
            self.content_only.setEnabled(not running)

    @Slot(int, str)
    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.status_label.setText(f"{percent}% · {message}")

    @Slot(object)
    def _on_completed(self, result: ConversionCompletion) -> None:
        self._completion = result
        self._set_running(False)
        self.progress.setValue(100)
        self.status_label.setText("轉換完成。")
        self.warnings.setPlainText("\n".join(result.warnings))
        self.cover_button.show()
        QMessageBox.information(self, "儲存完成", str(result.output_path))

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setText("轉換失敗。")
        self.warnings.setPlainText(message)

    @Slot()
    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setText("轉換已取消。")

    @Slot()
    def _emit_cover_payload(self) -> None:
        if self._completion is not None:
            self.open_cover_requested.emit(self._completion.to_cover_payload())
