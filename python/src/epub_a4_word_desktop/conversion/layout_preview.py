from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from epub_a4_word.page_placement import PagePlacement, build_page_placement
from epub_a4_word.pagination import LayoutSettings, resolve_layout


class LayoutPreview(QWidget):
    """Preview paper, content rectangle, and shared crop/fold geometry."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = resolve_layout(LayoutSettings(imposition_mode="signature16"))
        self._placement = build_page_placement(self._settings)
        self.setMinimumHeight(190)

    @property
    def placement(self) -> PagePlacement:
        return self._placement

    @property
    def finished_edge_message(self) -> str:
        if self._settings.imposition_mode in {"single_a5", "single_4x6"}:
            return "紙張邊緣即成品邊"
        return ""

    @property
    def reading_direction_message(self) -> str:
        if self._settings.writing_mode == "taiwan_vertical":
            return "直排：由上往下、欄位由右往左；右裝訂"
        return "橫排：由左往右；左裝訂"

    def set_settings(self, settings: LayoutSettings) -> None:
        self._settings = resolve_layout(settings)
        self._placement = build_page_placement(self._settings)
        self.setToolTip(self._tooltip_text())
        self.update()

    def _tooltip_text(self) -> str:
        placement = self._placement
        text = (
            f"紙張 {placement.paper_width_mm:g} × {placement.paper_height_mm:g} mm；"
            f"內容 {placement.content_width_mm:g} × {placement.content_height_mm:g} mm"
        )
        parts = [text, self.reading_direction_message]
        if self.finished_edge_message:
            parts.append(self.finished_edge_message)
        return "；".join(parts)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        available = self.rect().adjusted(12, 12, -12, -28)
        placement = self._placement
        scale = min(
            available.width() / placement.paper_width_mm,
            available.height() / placement.paper_height_mm,
        )
        width = placement.paper_width_mm * scale
        height = placement.paper_height_mm * scale
        left = available.center().x() - width / 2
        top = available.center().y() - height / 2
        page = QRectF(left, top, width, height)
        content = QRectF(
            left + placement.content_x_mm * scale,
            top + placement.content_y_mm * scale,
            placement.content_width_mm * scale,
            placement.content_height_mm * scale,
        )
        painter.fillRect(page, self.palette().base())
        painter.setPen(QPen(self.palette().text().color(), 1.0))
        painter.drawRect(page)
        painter.setPen(QPen(self.palette().highlight().color(), 1.25, Qt.PenStyle.DashLine))
        painter.drawRect(content)
        for guide in placement.guides:
            style = Qt.PenStyle.DashLine if guide.role == "fold" else Qt.PenStyle.SolidLine
            painter.setPen(QPen(self.palette().text().color(), 1.0, style))
            painter.drawLine(
                QLineF(
                    left + guide.x1_mm * scale,
                    top + guide.y1_mm * scale,
                    left + guide.x2_mm * scale,
                    top + guide.y2_mm * scale,
                )
            )
        painter.setPen(self.palette().highlight().color())
        if self._settings.writing_mode == "taiwan_vertical":
            painter.drawText(
                content,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                "↓　↓　↓\n← 欄位\n右裝訂",
            )
        else:
            painter.drawText(
                content,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                "→ 橫排\n左裝訂",
            )
        if self.finished_edge_message:
            painter.setPen(self.palette().text().color())
            painter.drawText(
                self.rect().adjusted(8, self.height() - 24, -8, -4),
                Qt.AlignmentFlag.AlignCenter,
                self.finished_edge_message,
            )


# Backward-compatible import name used by older tests and integrations.
B6OnA5Preview = LayoutPreview
