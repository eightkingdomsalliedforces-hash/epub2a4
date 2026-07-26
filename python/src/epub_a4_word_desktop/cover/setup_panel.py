from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.models import ImageMode
from epub_a4_word.cover.service import inspect_source


@dataclass(frozen=True)
class CoverSetupValues:
    source_path: Path
    trim_size_mm: tuple[float, float]
    page_count: int
    paper_caliper_mm: float
    manual_spine_width_mm: float | None
    bleed_mm: float
    image_mode: ImageMode
    template_id: str
    confirmed_back_cover_asset_id: str | None = None

    def settings(self, working_dir: Path | str) -> dict[str, Any]:
        return {
            "working_dir": str(Path(working_dir).expanduser().resolve()),
            "trim_width_mm": self.trim_size_mm[0],
            "trim_height_mm": self.trim_size_mm[1],
            "page_count": self.page_count,
            "paper_caliper_mm": self.paper_caliper_mm,
            "manual_spine_width_mm": self.manual_spine_width_mm,
            "bleed_mm": self.bleed_mm,
            "overlap_mm": 5.0,
            "dpi": 300,
            "show_crop_marks": True,
            "show_assembly_marks": True,
            "image_mode": self.image_mode.value,
            **(
                {"confirmed_back_cover_asset_id": self.confirmed_back_cover_asset_id}
                if self.confirmed_back_cover_asset_id
                else {}
            ),
        }


class CoverSetupPanel(QWidget):
    create_requested = Signal(object)
    error = Signal(str)

    PAPER_PRESETS = (
        ("70 gsm", 0.09),
        ("80 gsm", 0.10),
        ("100 gsm", 0.12),
        ("120 gsm", 0.14),
    )
    TRIM_PRESETS = (
        ("A5", (148.0, 210.0)),
        ("B6", (128.0, 182.0)),
        ("A6", (105.0, 148.0)),
        ("4×6 英吋", (101.6, 152.4)),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cover-setup-panel")
        self.source_edit = QLineEdit(self)
        self.source_edit.setPlaceholderText("選擇 EPUB、DOCX 或 PDF")
        self.browse_button = QPushButton("瀏覽…", self)
        source_row = QWidget(self)
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(self.browse_button)

        self.trim_combo = QComboBox(self)
        for label, size in self.TRIM_PRESETS:
            self.trim_combo.addItem(label, size)

        self.page_count_spin = QSpinBox(self)
        self.page_count_spin.setRange(1, 1_000_000)
        self.page_count_spin.setValue(160)
        self.page_count_confirmed = QCheckBox("我已確認正文頁數", self)
        self.page_count_note = QLabel("", self)
        self.cover_status_note = QLabel("", self)
        self.confirm_back_cover = QCheckBox("將可能的封底作為封底使用", self)
        self.confirm_back_cover.setVisible(False)
        self._back_cover_candidate_asset_id: str | None = None

        self.paper_combo = QComboBox(self)
        for label, caliper in self.PAPER_PRESETS:
            self.paper_combo.addItem(label, caliper)
        self.caliper_spin = QDoubleSpinBox(self)
        self.caliper_spin.setRange(0.01, 1.00)
        self.caliper_spin.setDecimals(3)
        self.caliper_spin.setSingleStep(0.005)
        self.caliper_spin.setSuffix(" mm／張")
        self.caliper_spin.setValue(0.10)

        self.spine_label = QLabel(self)
        self.manual_spine_enabled = QCheckBox("手動指定書脊寬度", self)
        self.manual_spine_spin = QDoubleSpinBox(self)
        self.manual_spine_spin.setRange(0.01, 500.0)
        self.manual_spine_spin.setDecimals(3)
        self.manual_spine_spin.setSuffix(" mm")
        self.manual_spine_spin.setEnabled(False)

        self.bleed_spin = QDoubleSpinBox(self)
        self.bleed_spin.setRange(0.0, 10.0)
        self.bleed_spin.setDecimals(2)
        self.bleed_spin.setValue(0.0)
        self.bleed_spin.setSuffix(" mm")
        self.bleed_spin.setToolTip(
            "裁切外延只用於印刷廠裁切時避免白邊，與圖片產生無關；家用列印可保持 0 mm。"
        )

        self.image_mode_combo = QComboBox(self)
        self.image_mode_combo.addItem("只有正面圖片", ImageMode.FRONT_ONLY.value)
        self.image_mode_combo.addItem("完整展開圖片", ImageMode.FULL_SPREAD.value)

        self.template_combo = QComboBox(self)
        self.template_combo.addItem("原始封面（不加文字）", "minimal")
        self.template_combo.addItem("上下色塊", "top_bottom_blocks")
        self.template_combo.addItem("全圖覆蓋", "full_bleed_image")
        self.template_combo.addItem("經典書籍", "classic_book")
        self.template_combo.addItem("出版社式封底", "publisher_back_matter")
        self.create_button = QPushButton("建立／更新封面專案", self)
        self.create_button.setEnabled(False)

        form = QFormLayout()
        form.addRow("來源", source_row)
        form.addRow("成品尺寸", self.trim_combo)
        form.addRow("正文頁數", self.page_count_spin)
        form.addRow("", self.page_count_confirmed)
        form.addRow("", self.page_count_note)
        form.addRow("封面辨識", self.cover_status_note)
        form.addRow("", self.confirm_back_cover)
        form.addRow("紙張預設", self.paper_combo)
        form.addRow("紙張厚度", self.caliper_spin)
        form.addRow("自動書脊", self.spine_label)
        form.addRow("", self.manual_spine_enabled)
        form.addRow("手動書脊", self.manual_spine_spin)
        form.addRow("裁切外延（出血）", self.bleed_spin)
        form.addRow("圖片模式", self.image_mode_combo)
        form.addRow("初始模板", self.template_combo)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addWidget(self.create_button)

        self.page_count = self.page_count_spin
        self.page_confirmed = self.page_count_confirmed
        self.trim = self.trim_combo
        self.paper = self.paper_combo
        self.caliper = self.caliper_spin
        self.bleed = self.bleed_spin

        self.browse_button.clicked.connect(self._browse)
        self.source_edit.textChanged.connect(self._update_create_enabled)
        self.page_count_confirmed.toggled.connect(self._update_create_enabled)
        self.page_count_spin.valueChanged.connect(self._update_spine)
        self.trim_combo.currentIndexChanged.connect(self._trim_changed)
        self.paper_combo.currentIndexChanged.connect(self._paper_changed)
        self.caliper_spin.valueChanged.connect(self._update_spine)
        self.manual_spine_enabled.toggled.connect(self.manual_spine_spin.setEnabled)
        self.create_button.clicked.connect(self._emit_create)
        self._paper_changed(self.paper_combo.currentIndex())

    @property
    def source_path(self) -> Path | None:
        text = self.source_edit.text().strip()
        return Path(text) if text else None

    @property
    def automatic_spine_width_mm(self) -> float:
        return math.ceil(self.page_count_spin.value() / 2) * self.caliper_spin.value()

    def _update_spine(self, _value: object = None) -> None:
        self.spine_label.setText(f"{self.automatic_spine_width_mm:.3f} mm")

    def _paper_changed(self, index: int) -> None:
        value = self.paper_combo.itemData(index)
        if value is not None:
            self.caliper_spin.setValue(float(value))
        self._update_spine()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇正文來源",
            "",
            "支援文件 (*.epub *.docx *.pdf)",
        )
        if path:
            try:
                self.inspect_source_path(path)
            except Exception as exc:
                self.set_source(path)
                self.page_count_note.setText(f"無法自動取得頁數：{exc}")
                self.error.emit(str(exc))

    def inspect_source_path(self, source_path: Path | str) -> None:
        trim = self.trim_combo.currentData()
        inspection = inspect_source(
            str(Path(source_path)), float(trim[0]), float(trim[1])
        )
        self.load_inspection(inspection)

    def _trim_changed(self, _index: int) -> None:
        source = self.source_path
        if source is None or not source.is_file():
            return
        try:
            self.inspect_source_path(source)
        except Exception as exc:
            self.page_count_note.setText(f"無法重新估算頁數：{exc}")
            self.error.emit(str(exc))

    def _update_create_enabled(self, _value: object = None) -> None:
        self.create_button.setEnabled(
            self.source_path is not None and self.page_count_confirmed.isChecked()
        )

    def set_source(
        self,
        source_path: Path | str,
        *,
        page_count: int | None = None,
        estimated: bool = False,
        confirmed: bool = False,
    ) -> None:
        self.source_edit.setText(str(Path(source_path)))
        if page_count is not None:
            self.page_count_spin.setValue(int(page_count))
        self.page_count_confirmed.setChecked(bool(confirmed and not estimated))
        self.page_count_note.setText("估算頁數，請核對後勾選確認。" if estimated else "")
        self._update_create_enabled()

    def load_inspection(self, inspection: dict[str, object]) -> None:
        source = inspection.get("source_path")
        if source:
            self.source_edit.setText(str(source))
        count = inspection.get("fixed_page_count") or inspection.get("page_count")
        metadata = inspection.get("metadata")
        estimated = False
        if isinstance(metadata, dict):
            estimated = bool(metadata.get("page_count_is_estimate", False))
            embedded = metadata.get("embedded_images", ())
            roles = {
                str(item.get("role", ""))
                for item in embedded
                if isinstance(item, dict)
            } if isinstance(embedded, (list, tuple)) else set()
            front_status = (
                "已找到正面封面"
                if roles.intersection({"cover", "front_cover"})
                else "未找到正面封面"
            )
            candidate = next(
                (
                    item
                    for item in embedded
                    if isinstance(item, dict)
                    and item.get("role") == "back_cover_candidate"
                    and isinstance(item.get("id"), str)
                    and str(item.get("id")).strip()
                ),
                None,
            ) if isinstance(embedded, (list, tuple)) else None
            if "back_cover" in roles:
                back_status = "已找到封底"
                self._back_cover_candidate_asset_id = None
                self.confirm_back_cover.setChecked(False)
                self.confirm_back_cover.setVisible(False)
            elif candidate is not None:
                back_status = "可能的封底需確認"
                self._back_cover_candidate_asset_id = str(candidate["id"])
                self.confirm_back_cover.setChecked(False)
                self.confirm_back_cover.setVisible(True)
            else:
                back_status = "未找到封底"
                self._back_cover_candidate_asset_id = None
                self.confirm_back_cover.setChecked(False)
                self.confirm_back_cover.setVisible(False)
            self.cover_status_note.setText(f"{front_status}；{back_status}")
        else:
            self._back_cover_candidate_asset_id = None
            self.confirm_back_cover.setChecked(False)
            self.confirm_back_cover.setVisible(False)
            self.cover_status_note.setText("")
        estimated = bool(inspection.get("page_count_estimated", estimated))
        if count is not None:
            self.page_count_spin.setValue(int(count))
            self.page_count_confirmed.setChecked(True)
            self.page_count_note.setText(
                "已依目前成品尺寸自動估算，可自行修改。"
                if estimated
                else "已自動取得文件頁數，可自行修改。"
            )
        else:
            self.page_count_confirmed.setChecked(False)
            self.page_count_note.setText("無法自動取得頁數，請手動輸入並確認。")
        self._update_create_enabled()

    def set_trim_size(self, width_mm: float, height_mm: float) -> None:
        target = (float(width_mm), float(height_mm))
        for index in range(self.trim_combo.count()):
            current = self.trim_combo.itemData(index)
            if current and all(
                abs(float(a) - float(b)) < 1e-6 for a, b in zip(current, target)
            ):
                self.trim_combo.setCurrentIndex(index)
                return
        raise ValueError("不支援的封面成品尺寸。")

    def values(self) -> CoverSetupValues:
        source = self.source_path
        if source is None:
            raise ValueError("請選擇 EPUB、DOCX 或 PDF。")
        if source.suffix.lower() not in {".epub", ".docx", ".pdf"}:
            raise ValueError("來源必須是 EPUB、DOCX 或 PDF。")
        if not self.page_count_confirmed.isChecked():
            raise ValueError("請確認正文頁數。")
        trim = self.trim_combo.currentData()
        manual = self.manual_spine_spin.value() if self.manual_spine_enabled.isChecked() else None
        return CoverSetupValues(
            source_path=source,
            trim_size_mm=(float(trim[0]), float(trim[1])),
            page_count=self.page_count_spin.value(),
            paper_caliper_mm=self.caliper_spin.value(),
            manual_spine_width_mm=manual,
            bleed_mm=self.bleed_spin.value(),
            image_mode=ImageMode(str(self.image_mode_combo.currentData())),
            template_id=str(self.template_combo.currentData()),
            confirmed_back_cover_asset_id=(
                self._back_cover_candidate_asset_id
                if self.confirm_back_cover.isChecked()
                else None
            ),
        )

    def _emit_create(self) -> None:
        self.create_requested.emit(self.values())
