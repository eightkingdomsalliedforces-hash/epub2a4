from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.composition import CompositionSelection
from epub_a4_word.cover.search.models import CandidateCategory

_LABELS = {
    CandidateCategory.FRONT: "正面",
    CandidateCategory.BACK: "背面",
    CandidateCategory.SPINE: "書脊",
    CandidateCategory.FULL_SPREAD: "完整書衣",
}


class _SelectionControls(QGroupBox):
    def __init__(self, category: CandidateCategory, path: Path, parent=None) -> None:
        super().__init__(_LABELS[category], parent)
        self.category = category
        self.path = Path(path)
        self.crop_left = self._spin(0.0, 0.90, 0.01, 0.0)
        self.crop_top = self._spin(0.0, 0.90, 0.01, 0.0)
        self.crop_right = self._spin(0.0, 0.90, 0.01, 0.0)
        self.crop_bottom = self._spin(0.0, 0.90, 0.01, 0.0)
        self.scale = self._spin(0.10, 5.00, 0.05, 1.0)
        self.offset_x = self._spin(-1.00, 1.00, 0.02, 0.0)
        self.offset_y = self._spin(-1.00, 1.00, 0.02, 0.0)
        form = QFormLayout(self)
        path_label = QLabel(str(self.path), self)
        path_label.setWordWrap(True)
        form.addRow("圖片", path_label)
        form.addRow("左裁切比例", self.crop_left)
        form.addRow("上裁切比例", self.crop_top)
        form.addRow("右裁切比例", self.crop_right)
        form.addRow("下裁切比例", self.crop_bottom)
        form.addRow("縮放", self.scale)
        form.addRow("水平位移", self.offset_x)
        form.addRow("垂直位移", self.offset_y)

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float, value: float):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def value(self) -> CompositionSelection:
        if self.crop_left.value() + self.crop_right.value() >= 1.0:
            raise ValueError(f"{_LABELS[self.category]}的左右裁切總和必須小於 1。")
        if self.crop_top.value() + self.crop_bottom.value() >= 1.0:
            raise ValueError(f"{_LABELS[self.category]}的上下裁切總和必須小於 1。")
        return CompositionSelection(
            self.path,
            self.category,
            crop_left=self.crop_left.value(),
            crop_top=self.crop_top.value(),
            crop_right=self.crop_right.value(),
            crop_bottom=self.crop_bottom.value(),
            scale=self.scale.value(),
            offset_x=self.offset_x.value(),
            offset_y=self.offset_y.value(),
        )


class CompositionDialog(QDialog):
    def __init__(
        self,
        paths: dict[str, Path],
        *,
        mode: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("套用搜尋到的封面圖片")
        self.resize(560, 680)
        self.controls: list[_SelectionControls] = []

        intro = QLabel(
            "分區編輯會把圖片分別放進正面、背面與書脊，之後仍可在畫布裁切與移動。"
            if mode == "segmented"
            else "合成完整書衣會依背面 → 書脊 → 正面的印刷順序產生一張 PNG。可先調整各區裁切、縮放與位移。",
            self,
        )
        intro.setWordWrap(True)
        host = QWidget(self)
        host_layout = QVBoxLayout(host)
        for key, path in paths.items():
            category = CandidateCategory(key)
            if mode == "segmented" and category is CandidateCategory.FULL_SPREAD:
                continue
            control = _SelectionControls(category, Path(path), host)
            self.controls.append(control)
            host_layout.addWidget(control)
        host_layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)

    def selections(self) -> dict[CandidateCategory, CompositionSelection]:
        return {control.category: control.value() for control in self.controls}
