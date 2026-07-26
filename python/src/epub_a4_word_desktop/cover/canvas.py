from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import ElementKind
from epub_a4_word.cover.print_plan import build_print_plan
from epub_a4_word.cover.project_io import loads_project

from .guides import GuideLayer
from .items import CoverBarcodeItem, CoverImageItem, CoverTextItem


class ZoomControls(QWidget):
    fit_requested = Signal()
    actual_size_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.fit_button = QPushButton("符合視窗", self)
        self.actual_button = QPushButton("100%", self)
        self.label = QLabel("100%", self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.fit_button)
        layout.addWidget(self.actual_button)
        layout.addStretch(1)
        layout.addWidget(self.label)
        self.fit_button.clicked.connect(lambda _checked=False: self.fit_requested.emit())
        self.actual_button.clicked.connect(
            lambda _checked=False: self.actual_size_requested.emit()
        )


class CoverCanvas(QGraphicsView):
    """Interactive full-cover canvas where one scene unit is exactly one mm."""

    element_selected = Signal(object)
    element_transform_requested = Signal(str, dict)
    element_patch_requested = Signal(str, dict)
    MIN_ZOOM = 0.10
    MAX_ZOOM = 8.00
    PIXELS_PER_MM = 96.0 / 25.4

    def __init__(self, parent: QWidget | None = None) -> None:
        scene = QGraphicsScene()
        super().__init__(scene, parent)
        self.setObjectName("cover-canvas")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#d1d5db"))
        self.project_json = ""
        self.items_by_id: dict[
            str, CoverBarcodeItem | CoverImageItem | CoverTextItem
        ] = {}
        self.guide_layer = GuideLayer(scene)
        self._paper_item = None
        self._preview_item: QGraphicsPixmapItem | None = None
        self._zoom_factor = 1.0
        self.zoom_controls = ZoomControls()
        self.zoom_controls.fit_requested.connect(self.fit_in_view)
        self.zoom_controls.actual_size_requested.connect(lambda: self.set_zoom(1.0))
        scene.selectionChanged.connect(self._selection_changed)
        self.set_zoom(1.0)

    def set_project(self, project_json: str) -> None:
        project = loads_project(project_json)
        layout = calculate_layout(project)
        plan = build_print_plan(layout)
        scene = self.scene()
        scene.clear()
        self.items_by_id.clear()
        self.guide_layer = GuideLayer(scene)
        self._preview_item = None
        self.project_json = project_json
        scene.setSceneRect(
            layout.bleed_rect.x_mm,
            layout.bleed_rect.y_mm,
            layout.bleed_rect.width_mm,
            layout.bleed_rect.height_mm,
        )
        self._paper_item = scene.addRect(
            layout.bleed_rect.x_mm,
            layout.bleed_rect.y_mm,
            layout.bleed_rect.width_mm,
            layout.bleed_rect.height_mm,
        )
        self._paper_item.setBrush(QColor("white"))
        self._paper_item.setPen(Qt.PenStyle.NoPen)
        self._paper_item.setZValue(-20_000.0)
        self._paper_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        for element in sorted(project.elements, key=lambda item: item.z_index):
            item: CoverBarcodeItem | CoverImageItem | CoverTextItem | None
            if element.kind is ElementKind.IMAGE:
                item = CoverImageItem(element)
            elif element.kind is ElementKind.TEXT:
                item = CoverTextItem(element)
            elif element.kind is ElementKind.BARCODE_PLACEHOLDER:
                item = CoverBarcodeItem(element)
            else:
                item = None
            if item is None:
                continue
            item.transform_committed.connect(self._item_transform_committed)
            scene.addItem(item)
            self.items_by_id[element.id] = item

        self.guide_layer.rebuild(layout, plan)
        self.viewport().update()

    def set_preview(self, path: Path | str) -> None:
        if not self.project_json:
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        if self._preview_item is not None:
            self.scene().removeItem(self._preview_item)
        target = self.scene().sceneRect()
        scaled = pixmap.scaled(
            max(1, int(target.width() * 4)),
            max(1, int(target.height() * 4)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        item = self.scene().addPixmap(scaled)
        item.setPos(target.x(), target.y())
        item.setScale(target.width() / max(1.0, float(scaled.width())))
        item.setZValue(-19_000.0)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._preview_item = item

    def _selection_changed(self) -> None:
        selected = [
            item
            for item in self.scene().selectedItems()
            if hasattr(item, "element_id")
        ]
        element_id = selected[0].element_id if selected else None
        self.element_selected.emit(element_id)

    def select_element(self, element_id: str | None) -> None:
        self.scene().clearSelection()
        if element_id is None:
            self.element_selected.emit(None)
            return
        try:
            item = self.items_by_id[element_id]
        except KeyError as exc:
            raise KeyError(f"找不到畫布元素：{element_id}") from exc
        item.setSelected(True)
        self.centerOn(item)
        self.element_selected.emit(element_id)

    def _item_transform_committed(self, element_id: str, transform: dict) -> None:
        self.element_transform_requested.emit(element_id, dict(transform))

    def _commit_item_transform(
        self,
        element_id: str,
        rect: QRectF,
        rotation_deg: float,
    ) -> None:
        self.element_transform_requested.emit(
            element_id,
            {
                "x_mm": float(rect.x()),
                "y_mm": float(rect.y()),
                "width_mm": float(rect.width()),
                "height_mm": float(rect.height()),
                "rotation_deg": float(rotation_deg),
            },
        )

    def set_zoom(self, factor: float) -> None:
        self._zoom_factor = min(self.MAX_ZOOM, max(self.MIN_ZOOM, float(factor)))
        transform = QTransform()
        scale = self.PIXELS_PER_MM * self._zoom_factor
        transform.scale(scale, scale)
        self.setTransform(transform)
        self.zoom_controls.label.setText(f"{self._zoom_factor * 100:.0f}%")

    def fit_in_view(self) -> None:
        if self.scene().sceneRect().isEmpty():
            return
        padding_mm = 20.0 / self.PIXELS_PER_MM
        rect = self.scene().sceneRect().adjusted(
            -padding_mm,
            -padding_mm,
            padding_mm,
            padding_mm,
        )
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_factor = self.transform().m11() / self.PIXELS_PER_MM
        self.zoom_controls.label.setText(f"{self._zoom_factor * 100:.0f}%")

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            multiplier = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.set_zoom(self._zoom_factor * multiplier)
            event.accept()
            return
        selected = [
            item
            for item in self.scene().selectedItems()
            if isinstance(item, CoverImageItem)
        ]
        if len(selected) == 1 and event.angleDelta().y() != 0:
            item = selected[0]
            multiplier = 1.10 if event.angleDelta().y() > 0 else 1.0 / 1.10
            scale = min(5.0, max(0.1, item.content_scale * multiplier))
            item.set_content_scale(scale)
            self.element_patch_requested.emit(
                item.element_id, {"content": {"scale": scale}}
            )
            event.accept()
            return
        super().wheelEvent(event)
