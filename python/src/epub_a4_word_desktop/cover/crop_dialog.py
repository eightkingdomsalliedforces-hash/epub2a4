from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _CropPreview(QWidget):
    rect_changed = Signal(object)

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pixmap = pixmap
        self.normalized_rect = QRectF(0.0, 0.0, 1.0, 1.0)
        self._drag_start: QPointF | None = None
        self._start_rect = QRectF()
        self.setMinimumSize(480, 280)

    def set_normalized_rect(self, rect: QRectF) -> None:
        self.normalized_rect = QRectF(rect)
        self.update()

    def _image_rect(self) -> QRectF:
        if self.pixmap.isNull():
            return QRectF(self.rect())
        scaled = self.pixmap.size().scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        return QRectF(
            (self.width() - scaled.width()) / 2.0,
            (self.height() - scaled.height()) / 2.0,
            scaled.width(),
            scaled.height(),
        )

    def _display_crop_rect(self) -> QRectF:
        image = self._image_rect()
        crop = self.normalized_rect
        return QRectF(
            image.x() + crop.x() * image.width(),
            image.y() + crop.y() * image.height(),
            crop.width() * image.width(),
            crop.height() * image.height(),
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202124"))
        image_rect = self._image_rect()
        if not self.pixmap.isNull():
            painter.drawPixmap(image_rect.toRect(), self.pixmap)
        crop = self._display_crop_rect()
        overlay = QColor(0, 0, 0, 130)
        for area in (
            QRectF(
                image_rect.left(),
                image_rect.top(),
                image_rect.width(),
                crop.top() - image_rect.top(),
            ),
            QRectF(
                image_rect.left(),
                crop.bottom(),
                image_rect.width(),
                image_rect.bottom() - crop.bottom(),
            ),
            QRectF(
                image_rect.left(),
                crop.top(),
                crop.left() - image_rect.left(),
                crop.height(),
            ),
            QRectF(
                crop.right(),
                crop.top(),
                image_rect.right() - crop.right(),
                crop.height(),
            ),
        ):
            painter.fillRect(area, overlay)
        pen = QPen(QColor("white"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(crop)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._display_crop_rect().contains(event.position())
        ):
            self._drag_start = event.position()
            self._start_rect = QRectF(self.normalized_rect)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        image = self._image_rect()
        if image.width() <= 0 or image.height() <= 0:
            return
        delta = event.position() - self._drag_start
        x = self._start_rect.x() + delta.x() / image.width()
        y = self._start_rect.y() + delta.y() / image.height()
        x = max(0.0, min(1.0 - self._start_rect.width(), x))
        y = max(0.0, min(1.0 - self._start_rect.height(), y))
        self.normalized_rect.moveTo(x, y)
        self.rect_changed.emit(QRectF(self.normalized_rect))
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)


class CropDialog(QDialog):
    """Edit a normalized crop rectangle while project geometry remains in mm."""

    crop_changed = Signal(object)

    def __init__(
        self,
        source_path: Path | str,
        initial_rect: QRectF | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("裁切封面圖片")
        self.source_path = Path(source_path).expanduser().resolve()
        pixmap = QPixmap(str(self.source_path))
        if pixmap.isNull():
            raise ValueError("選取的圖片無法顯示。")
        self.preview = _CropPreview(pixmap, self)
        self.left_spin = self._spin()
        self.top_spin = self._spin()
        self.right_spin = self._spin()
        self.bottom_spin = self._spin()
        self.reset_button = QPushButton("重設", self)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )

        form = QFormLayout()
        form.addRow("左側裁切 %", self.left_spin)
        form.addRow("上側裁切 %", self.top_spin)
        form.addRow("右側裁切 %", self.right_spin)
        form.addRow("下側裁切 %", self.bottom_spin)
        fields = QWidget(self)
        fields.setLayout(form)
        side = QVBoxLayout()
        side.addWidget(fields)
        side.addWidget(self.reset_button)
        side.addStretch(1)
        body = QHBoxLayout()
        body.addWidget(self.preview, 1)
        body.addLayout(side)
        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(self.buttons)

        for spin in (
            self.left_spin,
            self.top_spin,
            self.right_spin,
            self.bottom_spin,
        ):
            spin.valueChanged.connect(self._fields_changed)
        self.preview.rect_changed.connect(self._preview_changed)
        self.reset_button.clicked.connect(
            lambda _checked=False: self.set_crop_rect(QRectF(0.0, 0.0, 1.0, 1.0))
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.set_crop_rect(initial_rect or QRectF(0.0, 0.0, 1.0, 1.0))

    @staticmethod
    def _spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 99.9)
        spin.setDecimals(2)
        spin.setSuffix(" %")
        spin.setSingleStep(0.5)
        return spin

    @staticmethod
    def _validated(rect: QRectF) -> QRectF:
        if rect.x() < 0.0 or rect.y() < 0.0:
            raise ValueError("裁切範圍必須位於圖片內。")
        if rect.width() <= 0.0 or rect.height() <= 0.0:
            raise ValueError("裁切範圍必須保留正面積。")
        if rect.right() > 1.0 + 1e-9 or rect.bottom() > 1.0 + 1e-9:
            raise ValueError("裁切範圍必須位於圖片內。")
        return QRectF(
            float(rect.x()),
            float(rect.y()),
            float(rect.width()),
            float(rect.height()),
        )

    def set_crop_rect(self, rect: QRectF) -> None:
        validated = self._validated(rect)
        self.preview.set_normalized_rect(validated)
        spins = (
            self.left_spin,
            self.top_spin,
            self.right_spin,
            self.bottom_spin,
        )
        values = (
            validated.x() * 100.0,
            validated.y() * 100.0,
            (1.0 - validated.right()) * 100.0,
            (1.0 - validated.bottom()) * 100.0,
        )
        for spin, value in zip(spins, values):
            blocked = spin.blockSignals(True)
            spin.setValue(max(0.0, value))
            spin.blockSignals(blocked)
        self.crop_changed.emit(QRectF(validated))

    def crop_rect(self) -> QRectF:
        return QRectF(self.preview.normalized_rect)

    def crop_margins(self) -> dict[str, float]:
        rect = self.crop_rect()
        return {
            "crop_left": rect.x(),
            "crop_top": rect.y(),
            "crop_right": 1.0 - rect.right(),
            "crop_bottom": 1.0 - rect.bottom(),
        }

    def _fields_changed(self, _value: float) -> None:
        left = self.left_spin.value() / 100.0
        top = self.top_spin.value() / 100.0
        right = self.right_spin.value() / 100.0
        bottom = self.bottom_spin.value() / 100.0
        width = 1.0 - left - right
        height = 1.0 - top - bottom
        if width <= 0.0 or height <= 0.0:
            return
        rect = QRectF(left, top, width, height)
        self.preview.set_normalized_rect(rect)
        self.crop_changed.emit(QRectF(rect))

    def _preview_changed(self, rect: QRectF) -> None:
        self.set_crop_rect(rect)
