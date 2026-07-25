from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget


class B6OnA5Preview(QWidget):
    """Informational preview of centered B6 content on an A5 sheet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._show_crop_marks = False
        self.setMinimumHeight(190)
        self.setToolTip("A5 紙張 148 × 210 mm；中央 B6 內容區 128 × 182 mm")

    def set_crop_marks(self, enabled: bool) -> None:
        self._show_crop_marks = bool(enabled)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        available = self.rect().adjusted(12, 12, -12, -12)
        scale = min(available.width() / 148.0, available.height() / 210.0)
        width = 148.0 * scale
        height = 210.0 * scale
        left = available.center().x() - width / 2
        top = available.center().y() - height / 2
        page = QRectF(left, top, width, height)
        trim = QRectF(
            left + 10.0 * scale,
            top + 14.0 * scale,
            128.0 * scale,
            182.0 * scale,
        )
        painter.fillRect(page, self.palette().base())
        painter.setPen(QPen(self.palette().text().color(), 1.0))
        painter.drawRect(page)
        painter.setPen(QPen(self.palette().highlight().color(), 1.5, Qt.PenStyle.DashLine))
        painter.drawRect(trim)
        if self._show_crop_marks:
            painter.setPen(QPen(self.palette().text().color(), 1.0))
            length = 5.0 * scale
            gap = 2.0 * scale
            for x in (trim.left(), trim.right()):
                painter.drawLine(QLineF(x, trim.top() - gap - length, x, trim.top() - gap))
                painter.drawLine(QLineF(x, trim.bottom() + gap, x, trim.bottom() + gap + length))
            for y in (trim.top(), trim.bottom()):
                painter.drawLine(QLineF(trim.left() - gap - length, y, trim.left() - gap, y))
                painter.drawLine(QLineF(trim.right() + gap, y, trim.right() + gap + length, y))
