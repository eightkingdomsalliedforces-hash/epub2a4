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
    MIN_SIZE_MM = 1.0

    def __init__(self, element: CoverElement) -> None:
        super().__init__()
        self.element_id = element.id
        self._width_mm = float(element.transform.width_mm)
        self._height_mm = float(element.transform.height_mm)
        self._start_pos = QPointF()
        self._resize_corner: str | None = None
        self._resize_start_scene = QPointF()
        self._resize_start_pos = QPointF()
        self._resize_start_size = (self._width_mm, self._height_mm)
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

    def _corner_at(self, point: QPointF) -> str | None:
        rect = self.boundingRect()
        radius = self.HANDLE_SIZE_MM * 1.5
        corners = {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
        }
        return next(
            (name for name, corner in corners.items() if (point - corner).manhattanLength() <= radius),
            None,
        )

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._start_pos = QPointF(self.pos())
        corner = self._corner_at(event.pos()) if self.isSelected() else None
        if corner is not None and event.button() == Qt.MouseButton.LeftButton:
            self._resize_corner = corner
            self._resize_start_scene = QPointF(event.scenePos())
            self._resize_start_pos = QPointF(self.pos())
            self._resize_start_size = (self._width_mm, self._height_mm)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._resize_corner is None:
            super().mouseMoveEvent(event)
            return
        delta = event.scenePos() - self._resize_start_scene
        x0, y0 = self._resize_start_pos.x(), self._resize_start_pos.y()
        width0, height0 = self._resize_start_size
        left, top, right, bottom = x0, y0, x0 + width0, y0 + height0
        corner = self._resize_corner
        if "l" in corner:
            left += delta.x()
        else:
            right += delta.x()
        if "t" in corner:
            top += delta.y()
        else:
            bottom += delta.y()
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            if "l" in corner:
                right -= delta.x()
            else:
                left -= delta.x()
            if "t" in corner:
                bottom -= delta.y()
            else:
                top -= delta.y()
        width = max(self.MIN_SIZE_MM, right - left)
        height = max(self.MIN_SIZE_MM, bottom - top)
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            aspect = width0 / max(self.MIN_SIZE_MM, height0)
            if abs(width - width0) >= abs(height - height0) * aspect:
                height = width / aspect
            else:
                width = height * aspect
            if "l" in corner:
                left = right - width
            else:
                right = left + width
            if "t" in corner:
                top = bottom - height
            else:
                bottom = top + height
        self.prepareGeometryChange()
        self._width_mm = max(self.MIN_SIZE_MM, right - left)
        self._height_mm = max(self.MIN_SIZE_MM, bottom - top)
        self.setPos(left, top)
        self.setTransformOriginPoint(self._width_mm / 2.0, self._height_mm / 2.0)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._resize_corner is not None:
            self._resize_corner = None
            self._emit_transform()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self.pos() != self._start_pos:
            self._emit_transform()

    def _emit_transform(self) -> None:
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
            painter.drawRect(QRectF(point.x() - half, point.y() - half, self.HANDLE_SIZE_MM, self.HANDLE_SIZE_MM))
        rotation_center = QPointF(rect.center().x(), rect.top() - 5.0)
        painter.drawLine(rect.center().x(), rect.top(), rotation_center.x(), rotation_center.y())
        painter.drawEllipse(rotation_center, half, half)
        painter.restore()


class CoverImageItem(CoverElementItem):
    def __init__(self, element: CoverElement, pixmap: QPixmap | None = None) -> None:
        super().__init__(element)
        self._content = dict(element.content)
        self._pixmap = pixmap or QPixmap(str(Path(str(element.content.get("path", "")))))

    @property
    def content_scale(self) -> float:
        return min(5.0, max(0.1, float(self._content.get("scale", 1.0))))

    def set_content_scale(self, value: float) -> None:
        self._content["scale"] = min(5.0, max(0.1, float(value)))
        self.update()

    def _source_rect(self) -> QRectF:
        width = float(self._pixmap.width())
        height = float(self._pixmap.height())
        crop = self._content.get("crop")
        if isinstance(crop, dict):
            left = min(1.0, max(0.0, float(crop.get("left", 0.0))))
            top = min(1.0, max(0.0, float(crop.get("top", 0.0))))
            right = min(1.0, max(left, float(crop.get("right", 1.0))))
            bottom = min(1.0, max(top, float(crop.get("bottom", 1.0))))
        else:
            left = min(1.0, max(0.0, float(self._content.get("crop_left", 0.0))))
            top = min(1.0, max(0.0, float(self._content.get("crop_top", 0.0))))
            right = 1.0 - min(1.0, max(0.0, float(self._content.get("crop_right", 0.0))))
            bottom = 1.0 - min(1.0, max(0.0, float(self._content.get("crop_bottom", 0.0))))
        return QRectF(left * width, top * height, max(1.0, (right - left) * width), max(1.0, (bottom - top) * height))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option, widget
        target = self.boundingRect()
        if self._pixmap.isNull():
            painter.fillRect(target, QColor("#e5e7eb"))
            painter.setPen(QColor("#6b7280"))
            painter.drawText(target, Qt.AlignmentFlag.AlignCenter, "圖片無法載入")
        else:
            source = self._source_rect()
            fit = str(self._content.get("fit", "cover")).casefold()
            contain = min(target.width() / source.width(), target.height() / source.height())
            ratio = max(target.width() / source.width(), target.height() / source.height()) if fit == "cover" else contain
            ratio *= self.content_scale
            width = source.width() * ratio
            height = source.height() * ratio
            offset_x = min(1.0, max(-1.0, float(self._content.get("offset_x", self._content.get("crop_x", 0.0)))))
            offset_y = min(1.0, max(-1.0, float(self._content.get("offset_y", self._content.get("crop_y", 0.0)))))
            destination = QRectF(
                (target.width() - width) / 2.0 + offset_x * target.width(),
                (target.height() - height) / 2.0 + offset_y * target.height(),
                width,
                height,
            )
            painter.save()
            painter.setClipRect(target)
            painter.drawPixmap(destination, self._pixmap, source)
            painter.restore()
        self._paint_selection_handles(painter)


class CoverTextItem(CoverElementItem):
    def __init__(self, element: CoverElement) -> None:
        super().__init__(element)
        self._content = dict(element.content)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
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
