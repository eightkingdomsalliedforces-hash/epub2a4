from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from epub_a4_word.cover.models import CoverElement


class CoverElementItem(QGraphicsObject):
    """Base scene item whose local geometry and position are expressed in mm."""

    transform_committed = Signal(str, dict)
    HANDLE_SIZE_MM = 2.5

    def __init__(self, element: CoverElement) -> None:
        super().__init__()
        self.element_id = element.id
        self._width_mm = float(element.transform.width_mm)
        self._height_mm = float(element.transform.height_mm)
        self._start_pos = QPointF()
        self.setPos(element.transform.x_mm, element.transform.y_mm)
        self.setRotation(element.transform.rotation_deg)
        self.setTransformOriginPoint(self._width_mm / 2.0, self._height_mm / 2.0)
        self.setOpacity(element.opacity)
        self.setZValue(element.z_index)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        return QRectF(0.0, 0.0, self._width_mm, self._height_mm)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._start_pos = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().mouseReleaseEvent(event)
        if self.pos() != self._start_pos:
            self.transform_committed.emit(
                self.element_id,
                {
                    "x_mm": float(self.x()),
                    "y_mm": float(self.y()),
                    "width_mm": self._width_mm,
                    "height_mm": self._height_mm,
                    "rotation_deg": float(self.rotation()),
                },
            )

    def _paint_selection_handles(self, painter: QPainter) -> None:
        if not self.isSelected():
            return
        painter.save()
        painter.setPen(QPen(QColor("#2563eb"), 0.0))
        painter.setBrush(QColor("white"))
        rect = self.boundingRect()
        half = self.HANDLE_SIZE_MM / 2.0
        for point in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
            painter.drawRect(
                QRectF(
                    point.x() - half,
                    point.y() - half,
                    self.HANDLE_SIZE_MM,
                    self.HANDLE_SIZE_MM,
                )
            )
        rotation_center = QPointF(rect.center().x(), rect.top() - 5.0)
        painter.drawLine(rect.center().x(), rect.top(), rotation_center.x(), rotation_center.y())
        painter.drawEllipse(rotation_center, half, half)
        painter.restore()


class CoverImageItem(CoverElementItem):
    def __init__(self, element: CoverElement, pixmap: QPixmap | None = None) -> None:
        super().__init__(element)
        source = pixmap or QPixmap(str(Path(str(element.content.get("path", "")))))
        self._pixmap = source
        self._fit = str(element.content.get("fit", "cover"))

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        target = self.boundingRect()
        if self._pixmap.isNull():
            painter.fillRect(target, QColor("#e5e7eb"))
            painter.setPen(QColor("#6b7280"))
            painter.drawText(target, Qt.AlignmentFlag.AlignCenter, "圖片無法載入")
        else:
            mode = (
                Qt.AspectRatioMode.KeepAspectRatio
                if self._fit == "contain"
                else Qt.AspectRatioMode.KeepAspectRatioByExpanding
            )
            scaled = self._pixmap.scaled(
                max(1, int(target.width() * 4)),
                max(1, int(target.height() * 4)),
                mode,
                Qt.TransformationMode.SmoothTransformation,
            )
            source = QRectF(0.0, 0.0, float(scaled.width()), float(scaled.height()))
            if self._fit != "contain":
                target_ratio = target.width() / target.height()
                source_ratio = source.width() / source.height()
                if source_ratio > target_ratio:
                    desired = source.height() * target_ratio
                    source.setLeft((source.width() - desired) / 2.0)
                    source.setWidth(desired)
                else:
                    desired = source.width() / target_ratio
                    source.setTop((source.height() - desired) / 2.0)
                    source.setHeight(desired)
            painter.drawPixmap(target, scaled, source)
        self._paint_selection_handles(painter)


class CoverTextItem(CoverElementItem):
    def __init__(self, element: CoverElement) -> None:
        super().__init__(element)
        self._content = dict(element.content)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.save()
        font = QFont(str(self._content.get("font_family", "Sans Serif")))
        font.setPointSizeF(float(self._content.get("font_size_pt", 18.0)))
        font.setWeight(QFont.Weight(int(self._content.get("font_weight", 400))))
        painter.setFont(font)
        painter.setPen(QColor(str(self._content.get("color", "#111827"))))
        alignment = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(str(self._content.get("align", "left")), Qt.AlignmentFlag.AlignLeft)
        painter.drawText(
            self.boundingRect(),
            alignment | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            str(self._content.get("text", "")),
        )
        painter.restore()
        self._paint_selection_handles(painter)
