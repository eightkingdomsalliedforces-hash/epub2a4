from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class B6OnA5Preview(QWidget):
    """Informational preview of centered B6 content on physical A5 paper."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("b6-on-a5-preview")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(220)
        self.mark_mode = "normal"

    def sizeHint(self) -> QSize:
        return QSize(220, 260)

    def set_mark_mode(self, mode: str) -> None:
        if mode not in {"normal", "crop_marks"}:
            raise ValueError(f"未知列印標記模式：{mode}")
        if self.mark_mode == mode:
            return
        self.mark_mode = mode
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API name
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        palette = self.palette()
        available = self.rect().adjusted(12, 12, -12, -12)
        label_height = 22.0
        scale = min(
            available.width() / 148.0,
            max(1.0, available.height() - label_height) / 210.0,
        )
        paper_width = 148.0 * scale
        paper_height = 210.0 * scale
        paper_left = available.center().x() - paper_width / 2.0
        paper_top = available.top()
        paper = QRectF(paper_left, paper_top, paper_width, paper_height)

        painter.fillRect(paper, palette.base())
        painter.setPen(QPen(palette.mid().color(), 1.2))
        painter.drawRect(paper)

        trim = QRectF(
            paper.left() + 10.0 * scale,
            paper.top() + 14.0 * scale,
            128.0 * scale,
            182.0 * scale,
        )
        trim_pen = QPen(palette.highlight().color(), 1.3, Qt.PenStyle.DashLine)
        painter.setPen(trim_pen)
        painter.drawRect(trim)

        if self.mark_mode == "crop_marks":
            painter.setPen(QPen(palette.text().color(), 1.0))
            gap = 2.0 * scale
            length = 5.0 * scale
            left = trim.left()
            right = trim.right()
            top = trim.top()
            bottom = trim.bottom()
            segments = (
                (left - gap - length, top, left - gap, top),
                (left, top - gap - length, left, top - gap),
                (right + gap, top, right + gap + length, top),
                (right, top - gap - length, right, top - gap),
                (left - gap - length, bottom, left - gap, bottom),
                (left, bottom + gap, left, bottom + gap + length),
                (right + gap, bottom, right + gap + length, bottom),
                (right, bottom + gap, right, bottom + gap + length),
            )
            for x1, y1, x2, y2 in segments:
                painter.drawLine(round(x1), round(y1), round(x2), round(y2))

        painter.setPen(palette.text().color())
        painter.drawText(
            paper.adjusted(6, 4, -6, -4),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "A5 紙張",
        )
        painter.drawText(
            trim.adjusted(6, 4, -6, -4),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "B6 128 × 182 mm",
        )
