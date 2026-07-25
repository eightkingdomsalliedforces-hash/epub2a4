from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from epub_a4_word.cover.geometry import CoverLayout, RectMm
from epub_a4_word.cover.print_plan import PrintPlan


def _pen(color: str, style: Qt.PenStyle = Qt.PenStyle.SolidLine) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(0.0)
    pen.setStyle(style)
    pen.setCosmetic(True)
    return pen


class GuideLayer:
    """Locked editor-only guides which never enter CoverProject JSON."""

    def __init__(self, scene: QGraphicsScene) -> None:
        self.scene = scene
        self.items: dict[str, list[QGraphicsItem]] = {}

    def _add_rect(self, group: str, rect: RectMm, pen: QPen) -> None:
        item = self.scene.addRect(
            rect.x_mm,
            rect.y_mm,
            rect.width_mm,
            rect.height_mm,
            pen,
        )
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        item.setZValue(10_000.0)
        self.items.setdefault(group, []).append(item)

    def _add_line(
        self,
        group: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        pen: QPen,
    ) -> None:
        item = self.scene.addLine(x1, y1, x2, y2, pen)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        item.setZValue(10_000.0)
        self.items.setdefault(group, []).append(item)

    def rebuild(self, layout: CoverLayout, plan: PrintPlan) -> None:
        self.clear()
        self._add_rect("bleed", layout.bleed_rect, _pen("#dc2626"))
        for rect in (layout.back_rect, layout.spine_rect, layout.front_rect):
            self._add_rect("regions", rect, _pen("#2563eb"))
        for rect in (
            layout.back_safe_rect,
            layout.spine_safe_rect,
            layout.front_safe_rect,
        ):
            self._add_rect("safe", rect, _pen("#16a34a", Qt.PenStyle.DashLine))

        for x_mm in (layout.spine_rect.x_mm, layout.spine_rect.right_mm):
            self._add_line(
                "folds",
                x_mm,
                layout.bleed_rect.y_mm,
                x_mm,
                layout.bleed_rect.bottom_mm,
                _pen("#7c3aed", Qt.PenStyle.DashDotLine),
            )

        if plan.mode == "single":
            self._add_rect("pages", plan.pages[0].source_rect, _pen("#374151"))
        else:
            for page in plan.pages:
                self._add_rect(
                    "pages",
                    page.source_rect,
                    _pen("#374151", Qt.PenStyle.DotLine),
                )
            overlap = 5.0
            left = RectMm(
                max(layout.back_rect.x_mm, layout.spine_rect.x_mm - overlap),
                layout.bleed_rect.y_mm,
                min(overlap, layout.spine_rect.x_mm - layout.back_rect.x_mm),
                layout.bleed_rect.height_mm,
            )
            right = RectMm(
                layout.spine_rect.right_mm,
                layout.bleed_rect.y_mm,
                min(overlap, layout.front_rect.right_mm - layout.spine_rect.right_mm),
                layout.bleed_rect.height_mm,
            )
            if left.width_mm > 0:
                self._add_rect(
                    "overlap", left, _pen("#d97706", Qt.PenStyle.DashLine)
                )
            if right.width_mm > 0:
                self._add_rect(
                    "overlap", right, _pen("#d97706", Qt.PenStyle.DashLine)
                )

    def set_group_visible(self, group: str, visible: bool) -> None:
        for item in self.items.get(group, []):
            item.setVisible(visible)

    def clear(self) -> None:
        for group in self.items.values():
            for item in group:
                self.scene.removeItem(item)
        self.items.clear()
