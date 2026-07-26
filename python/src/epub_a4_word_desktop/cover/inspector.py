from __future__ import annotations

from contextlib import ExitStack

from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.models import CoverElement, ElementKind


def _mm_spin() -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(-10_000.0, 10_000.0)
    spin.setDecimals(3)
    spin.setSingleStep(0.25)
    spin.setSuffix(" mm")
    return spin


class ElementInspector(QWidget):
    patch_requested = Signal(str, dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("element-inspector")
        self.element_id: str | None = None
        self.element_kind: ElementKind | None = None
        self.title_label = QLabel("未選取元素", self)

        self.x_spin = _mm_spin()
        self.y_spin = _mm_spin()
        self.width_spin = _mm_spin()
        self.height_spin = _mm_spin()
        self.width_spin.setMinimum(0.001)
        self.height_spin.setMinimum(0.001)
        self.rotation_spin = QDoubleSpinBox(self)
        self.rotation_spin.setRange(-3600.0, 3600.0)
        self.rotation_spin.setDecimals(2)
        self.rotation_spin.setSuffix("°")
        self.opacity_spin = QDoubleSpinBox(self)
        self.opacity_spin.setRange(0.0, 100.0)
        self.opacity_spin.setDecimals(1)
        self.opacity_spin.setSuffix("%")

        geometry_box = QGroupBox("位置與尺寸", self)
        geometry_form = QFormLayout(geometry_box)
        geometry_form.addRow("X", self.x_spin)
        geometry_form.addRow("Y", self.y_spin)
        geometry_form.addRow("寬", self.width_spin)
        geometry_form.addRow("高", self.height_spin)
        geometry_form.addRow("旋轉", self.rotation_spin)
        geometry_form.addRow("不透明度", self.opacity_spin)

        self.type_stack = QStackedWidget(self)
        self.empty_page = QLabel("選取文字或圖片以編輯內容。", self)
        self.type_stack.addWidget(self.empty_page)

        self.text_edit = QPlainTextEdit(self)
        self.font_family = QLineEdit(self)
        self.font_size_spin = QDoubleSpinBox(self)
        self.font_size_spin.setRange(1.0, 500.0)
        self.font_size_spin.setDecimals(1)
        self.font_weight_spin = QSpinBox(self)
        self.font_weight_spin.setRange(100, 900)
        self.font_weight_spin.setSingleStep(100)
        self.color_edit = QLineEdit(self)
        self.alignment_combo = QComboBox(self)
        self.alignment_combo.addItem("靠左", "left")
        self.alignment_combo.addItem("置中", "center")
        self.alignment_combo.addItem("靠右", "right")
        self.line_spacing_spin = QDoubleSpinBox(self)
        self.line_spacing_spin.setRange(0.5, 5.0)
        self.line_spacing_spin.setValue(1.2)
        self.direction_combo = QComboBox(self)
        self.direction_combo.addItem("水平", "horizontal")
        self.direction_combo.addItem("垂直", "vertical")
        self.apply_text_button = QPushButton("套用文字設定", self)
        text_page = QWidget(self)
        text_form = QFormLayout(text_page)
        text_form.addRow("文字", self.text_edit)
        text_form.addRow("字型", self.font_family)
        text_form.addRow("字級", self.font_size_spin)
        text_form.addRow("字重", self.font_weight_spin)
        text_form.addRow("顏色", self.color_edit)
        text_form.addRow("對齊", self.alignment_combo)
        text_form.addRow("行距", self.line_spacing_spin)
        text_form.addRow("方向", self.direction_combo)
        text_form.addRow(self.apply_text_button)
        self.text_page_index = self.type_stack.addWidget(text_page)

        self.fit_combo = QComboBox(self)
        self.fit_combo.addItem("填滿區域", "cover")
        self.fit_combo.addItem("符合區域", "contain")
        self.fit_combo.addItem("原始比例", "original")
        self.scale_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.scale_slider.setRange(10, 500)
        self.scale_slider.setValue(100)
        self.scale_slider.setSingleStep(5)
        self.scale_value_label = QLabel("100%", self)
        scale_row = QWidget(self)
        scale_layout = QHBoxLayout(scale_row)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.addWidget(self.scale_slider, 1)
        scale_layout.addWidget(self.scale_value_label)
        self.crop_x_spin = QDoubleSpinBox(self)
        self.crop_y_spin = QDoubleSpinBox(self)
        for spin in (self.crop_x_spin, self.crop_y_spin):
            spin.setRange(-1.0, 1.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.01)
        self.flip_horizontal = QCheckBox("水平翻轉", self)
        self.flip_vertical = QCheckBox("垂直翻轉", self)
        self.blur_spin = QDoubleSpinBox(self)
        self.blur_spin.setRange(0.0, 100.0)
        self.brightness_spin = QDoubleSpinBox(self)
        self.brightness_spin.setRange(0.0, 3.0)
        self.brightness_spin.setSingleStep(0.05)
        self.brightness_spin.setValue(1.0)
        self.overlay_spin = QDoubleSpinBox(self)
        self.overlay_spin.setRange(0.0, 1.0)
        self.overlay_spin.setDecimals(2)
        self.fit_button = QPushButton("符合區域", self)
        self.fill_button = QPushButton("填滿區域", self)
        self.original_button = QPushButton("原始比例", self)
        fit_row = QWidget(self)
        fit_layout = QHBoxLayout(fit_row)
        fit_layout.setContentsMargins(0, 0, 0, 0)
        fit_layout.addWidget(self.fit_button)
        fit_layout.addWidget(self.fill_button)
        fit_layout.addWidget(self.original_button)
        self.center_button = QPushButton("置中", self)
        self.reset_crop_button = QPushButton("重設裁切", self)
        reset_row = QWidget(self)
        reset_layout = QHBoxLayout(reset_row)
        reset_layout.setContentsMargins(0, 0, 0, 0)
        reset_layout.addWidget(self.center_button)
        reset_layout.addWidget(self.reset_crop_button)
        self.apply_image_button = QPushButton("套用圖片設定", self)
        image_page = QWidget(self)
        image_form = QFormLayout(image_page)
        image_form.addRow("縮放方式", self.fit_combo)
        image_form.addRow("縮放比例", scale_row)
        image_form.addRow("水平位置", self.crop_x_spin)
        image_form.addRow("垂直位置", self.crop_y_spin)
        image_form.addRow(fit_row)
        image_form.addRow(reset_row)
        image_form.addRow("", self.flip_horizontal)
        image_form.addRow("", self.flip_vertical)
        image_form.addRow("模糊", self.blur_spin)
        image_form.addRow("亮度", self.brightness_spin)
        image_form.addRow("暗色覆蓋", self.overlay_spin)
        image_form.addRow(self.apply_image_button)
        self.image_page_index = self.type_stack.addWidget(image_page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.title_label)
        layout.addWidget(geometry_box)
        layout.addWidget(self.type_stack)
        layout.addStretch(1)

        for field, name in (
            (self.x_spin, "x_mm"),
            (self.y_spin, "y_mm"),
            (self.width_spin, "width_mm"),
            (self.height_spin, "height_mm"),
            (self.rotation_spin, "rotation_deg"),
        ):
            field.editingFinished.connect(
                lambda name=name, field=field: self._emit_transform(name, field.value())
            )
        self.opacity_spin.editingFinished.connect(self._emit_opacity)
        self.apply_text_button.clicked.connect(self._emit_text)
        self.apply_image_button.clicked.connect(self._emit_image)
        self.scale_slider.valueChanged.connect(
            lambda value: self.scale_value_label.setText(f"{value}%")
        )
        self.scale_slider.sliderReleased.connect(self._emit_image)
        self.fit_button.clicked.connect(lambda _checked=False: self._emit_fit("contain"))
        self.fill_button.clicked.connect(lambda _checked=False: self._emit_fit("cover"))
        self.original_button.clicked.connect(lambda _checked=False: self._emit_fit("original"))
        self.center_button.clicked.connect(self._emit_center)
        self.reset_crop_button.clicked.connect(self._emit_reset_crop)
        self.setEnabled(False)

    def _controls(self) -> tuple[QWidget, ...]:
        return (
            self.x_spin,
            self.y_spin,
            self.width_spin,
            self.height_spin,
            self.rotation_spin,
            self.opacity_spin,
            self.text_edit,
            self.font_family,
            self.font_size_spin,
            self.font_weight_spin,
            self.color_edit,
            self.alignment_combo,
            self.line_spacing_spin,
            self.direction_combo,
            self.fit_combo,
            self.scale_slider,
            self.crop_x_spin,
            self.crop_y_spin,
            self.flip_horizontal,
            self.flip_vertical,
            self.blur_spin,
            self.brightness_spin,
            self.overlay_spin,
        )

    def set_element(self, element: CoverElement | None) -> None:
        self.element_id = None if element is None else element.id
        self.element_kind = None if element is None else element.kind
        self.setEnabled(element is not None)
        if element is None:
            self.title_label.setText("未選取元素")
            self.type_stack.setCurrentIndex(0)
            return
        with ExitStack() as stack:
            for control in self._controls():
                stack.enter_context(QSignalBlocker(control))
            self.title_label.setText(f"{element.id}（{element.kind.value}）")
            transform = element.transform
            self.x_spin.setValue(transform.x_mm)
            self.y_spin.setValue(transform.y_mm)
            self.width_spin.setValue(transform.width_mm)
            self.height_spin.setValue(transform.height_mm)
            self.rotation_spin.setValue(transform.rotation_deg)
            self.opacity_spin.setValue(element.opacity * 100.0)
            if element.kind is ElementKind.TEXT:
                self.type_stack.setCurrentIndex(self.text_page_index)
                self.text_edit.setPlainText(str(element.content.get("text", "")))
                self.font_family.setText(str(element.content.get("font_family", "")))
                self.font_size_spin.setValue(float(element.content.get("font_size_pt", 18.0)))
                self.font_weight_spin.setValue(int(element.content.get("font_weight", 400)))
                self.color_edit.setText(str(element.content.get("color", "#111827")))
                self._set_combo_data(self.alignment_combo, element.content.get("align", "left"))
                self.line_spacing_spin.setValue(float(element.content.get("line_spacing", 1.2)))
                self._set_combo_data(self.direction_combo, element.content.get("direction", "horizontal"))
            elif element.kind is ElementKind.IMAGE:
                self.type_stack.setCurrentIndex(self.image_page_index)
                self._set_combo_data(self.fit_combo, element.content.get("fit", "cover"))
                self.scale_slider.setValue(
                    round(min(5.0, max(0.1, float(element.content.get("scale", 1.0)))) * 100.0)
                )
                self.crop_x_spin.setValue(
                    float(element.content.get("offset_x", element.content.get("crop_x", 0.0)))
                )
                self.crop_y_spin.setValue(
                    float(element.content.get("offset_y", element.content.get("crop_y", 0.0)))
                )
                self.flip_horizontal.setChecked(bool(element.content.get("flip_horizontal", False)))
                self.flip_vertical.setChecked(bool(element.content.get("flip_vertical", False)))
                self.blur_spin.setValue(float(element.content.get("blur", 0.0)))
                self.brightness_spin.setValue(float(element.content.get("brightness", 1.0)))
                self.overlay_spin.setValue(float(element.content.get("dark_overlay", 0.0)))
            else:
                self.type_stack.setCurrentIndex(0)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _emit_transform(self, name: str, value: float) -> None:
        if self.element_id is not None:
            self.patch_requested.emit(self.element_id, {"transform": {name: float(value)}})

    def _emit_opacity(self) -> None:
        if self.element_id is not None:
            self.patch_requested.emit(
                self.element_id,
                {"opacity": self.opacity_spin.value() / 100.0},
            )

    def _emit_text(self) -> None:
        if self.element_id is None or self.element_kind is not ElementKind.TEXT:
            return
        self.patch_requested.emit(
            self.element_id,
            {
                "content": {
                    "text": self.text_edit.toPlainText(),
                    "font_family": self.font_family.text(),
                    "font_size_pt": self.font_size_spin.value(),
                    "font_weight": self.font_weight_spin.value(),
                    "color": self.color_edit.text() or "#111827",
                    "align": self.alignment_combo.currentData(),
                    "line_spacing": self.line_spacing_spin.value(),
                    "direction": self.direction_combo.currentData(),
                }
            },
        )

    def _emit_image(self) -> None:
        if self.element_id is None or self.element_kind is not ElementKind.IMAGE:
            return
        self.patch_requested.emit(
            self.element_id,
            {
                "content": {
                    "fit": self.fit_combo.currentData(),
                    "scale": self.scale_slider.value() / 100.0,
                    "offset_x": self.crop_x_spin.value(),
                    "offset_y": self.crop_y_spin.value(),
                    "flip_horizontal": self.flip_horizontal.isChecked(),
                    "flip_vertical": self.flip_vertical.isChecked(),
                    "blur": self.blur_spin.value(),
                    "brightness": self.brightness_spin.value(),
                    "dark_overlay": self.overlay_spin.value(),
                }
            },
        )

    def _emit_fit(self, fit: str) -> None:
        if self.element_id is None or self.element_kind is not ElementKind.IMAGE:
            return
        self.patch_requested.emit(
            self.element_id,
            {
                "content": {
                    "fit": fit,
                    "scale": 1.0,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                }
            },
        )

    def _emit_center(self) -> None:
        if self.element_id is not None and self.element_kind is ElementKind.IMAGE:
            self.patch_requested.emit(
                self.element_id,
                {"content": {"offset_x": 0.0, "offset_y": 0.0}},
            )

    def _emit_reset_crop(self) -> None:
        if self.element_id is not None and self.element_kind is ElementKind.IMAGE:
            self.patch_requested.emit(
                self.element_id,
                {
                    "content": {
                        "crop": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0},
                        "crop_left": 0.0,
                        "crop_top": 0.0,
                        "crop_right": 0.0,
                        "crop_bottom": 0.0,
                    }
                },
            )
