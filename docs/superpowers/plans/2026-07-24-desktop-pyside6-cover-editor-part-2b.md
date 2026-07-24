# Desktop PySide6 Cover Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default desktop Tkinter interface with a portable PySide6 application that preserves all existing conversion features and adds a full visual cover editor on Windows, macOS, and Linux.

**Architecture:** Build a thin desktop package around the shared `epub_a4_word` core. A main window owns navigation; conversion and cover workflows use separate controllers and pages. The cover canvas uses millimetres as scene coordinates, so zoom is presentation-only and cannot change export geometry.

**Tech Stack:** Python 3.13, PySide6 6.11.1, pytest, pytest-qt, Pillow, shared cover service, `QGraphicsScene`, `QUndoStack`, `QThreadPool`.

## Global Constraints

- This plan begins only after `2026-07-24-cover-core-export.md` passes its full test gate.
- PySide6 is the default GUI on Windows, macOS, and Linux.
- `--legacy-gui` opens a Tkinter compatibility window for one release only.
- The conversion workflow retains EPUB → A4 four-up/A6 signature/A5/4×6 and DOCX → A5/4×6 behavior.
- The cover tool accepts EPUB, DOCX, and PDF independently and can also receive actual page count and trim size from a completed conversion.
- Cover edits remain in `CoverProject` schema version `1`; desktop-specific state must not be written into project geometry.
- Scene coordinates, inspector values, and serialized positions use millimetres.
- Preview may be reduced resolution; PDF/DOCX export always delegates to the shared core.
- The desktop app performs no update check.
- Search UI is added by the later search/release plan; this plan supports EPUB-embedded and local images.

---

## Subpart B: Tasks 6–7

### Task 6: Build the millimetre-based QGraphicsScene cover canvas

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/canvas.py`
- Create: `python/src/epub_a4_word_desktop/cover/items.py`
- Create: `python/src/epub_a4_word_desktop/cover/guides.py`
- Create: `desktop/tests/test_cover_canvas.py`

**Interfaces:**
- Produces: `CoverCanvas.set_project(project_json)`.
- Emits: `element_selected(str | None)` and `element_transform_requested(str, dict)`.
- Scene coordinates equal millimetres; one scene unit is exactly `1 mm`.

- [ ] **Step 1: Write failing coordinate tests**

```python
def test_scene_rect_uses_layout_millimetres(qtbot, project_json):
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(project_json)
    layout = calculate_layout(loads_project(project_json))
    assert canvas.scene().sceneRect().width() == pytest.approx(layout.bleed_rect.width_mm)
    assert canvas.scene().sceneRect().height() == pytest.approx(layout.bleed_rect.height_mm)


def test_drag_emits_mm_transform(qtbot, project_json):
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(project_json)
    with qtbot.waitSignal(canvas.element_transform_requested) as signal:
        canvas._commit_item_transform("front-title", QRectF(12.5, 20.0, 80.0, 25.0), 0.0)
    assert signal.args == ["front-title", {
        "x_mm": 12.5, "y_mm": 20.0, "width_mm": 80.0, "height_mm": 25.0, "rotation_deg": 0.0
    }]
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_canvas.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement selectable image and text items**

Create `CoverImageItem(QGraphicsPixmapItem)` and `CoverTextItem(QGraphicsTextItem)` with:

- `ItemIsSelectable`, `ItemIsMovable`, and geometry-change flags;
- stable `element_id` property;
- bounding rect matching project width/height in scene millimetres;
- resize handles displayed only for the selected item;
- rotation handle for text and images;
- transform commit only on mouse release, not every mouse move.

Use preview-scale pixmaps for interaction; do not load 300 DPI export images into the scene.

```python
class CoverImageItem(QGraphicsPixmapItem):
    transform_committed = Signal(str, dict)

    def __init__(self, element: CoverElement, pixmap: QPixmap) -> None:
        super().__init__(pixmap)
        self.element_id = element.id
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setPos(element.transform.x_mm, element.transform.y_mm)
        self.setRotation(element.transform.rotation_deg)
        self._start_pos = self.pos()

    def mousePressEvent(self, event) -> None:
        self._start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self.pos() != self._start_pos:
            self.transform_committed.emit(self.element_id, {
                "x_mm": self.x(),
                "y_mm": self.y(),
            })


class CoverTextItem(QGraphicsTextItem):
    transform_committed = Signal(str, dict)

    def __init__(self, element: CoverElement) -> None:
        super().__init__(str(element.content["text"]))
        self.element_id = element.id
        self.setTextWidth(element.transform.width_mm)
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
```

- [ ] **Step 4: Draw non-exporting guides**

`guides.py` draws separate locked items for:

- outer bleed boundary;
- back/spine/front boundaries;
- safe rectangles;
- fold lines;
- A4 page boundary for single mode;
- 5 mm overlap regions for split mode.

Guide visibility flags are independent of project elements and never serialized.

```python
class GuideLayer:
    def __init__(self, scene: QGraphicsScene) -> None:
        self.scene = scene
        self.items: dict[str, list[QGraphicsItem]] = {}

    def rebuild(self, layout: CoverLayout, plan: PrintPlan) -> None:
        self.clear()
        self.items["regions"] = [
            self.scene.addRect(rect.x_mm, rect.y_mm, rect.width_mm, rect.height_mm)
            for rect in (layout.back, layout.spine, layout.front)
        ]
        self.items["safe"] = [
            self.scene.addRect(rect.x_mm, rect.y_mm, rect.width_mm, rect.height_mm)
            for rect in layout.safe_rects
        ]
        self.items["overlap"] = [
            self.scene.addRect(rect.x_mm, rect.y_mm, rect.width_mm, rect.height_mm)
            for rect in plan.overlap_rects
        ]
        for group in self.items.values():
            for item in group:
                item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                item.setZValue(10_000)

    def clear(self) -> None:
        for group in self.items.values():
            for item in group:
                self.scene.removeItem(item)
        self.items.clear()
```

- [ ] **Step 5: Implement zoom and fit controls**

- Ctrl+wheel zoom range: `10%..800%`.
- `fit_in_view()` keeps aspect ratio and adds 20 px padding.
- `100%` means `96 desktop pixels per 25.4 scene millimetres`; it affects only view transform.

```python
class CoverView(QGraphicsView):
    MIN_ZOOM = 0.10
    MAX_ZOOM = 8.00

    def set_zoom(self, factor: float) -> None:
        factor = min(self.MAX_ZOOM, max(self.MIN_ZOOM, factor))
        pixels_per_mm = 96.0 / 25.4
        transform = QTransform()
        transform.scale(pixels_per_mm * factor, pixels_per_mm * factor)
        self.setTransform(transform)

    def fit_in_view(self) -> None:
        rect = self.scene().sceneRect().adjusted(-5.2917, -5.2917, 5.2917, 5.2917)
        self.fitInView(rect, Qt.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            multiplier = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.transform().m11() / (96.0 / 25.4) * multiplier)
            event.accept()
            return
        super().wheelEvent(event)
```

- [ ] **Step 6: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_canvas.py -q
git add python/src/epub_a4_word_desktop/cover desktop/tests/test_cover_canvas.py
git commit -m "feat: add millimetre-based desktop cover canvas"
```

Expected: PASS.

---

### Task 7: Add cover setup, inspector, layers, and template controls

**Files:**
- Create: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Create: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Create: `python/src/epub_a4_word_desktop/cover/inspector.py`
- Create: `python/src/epub_a4_word_desktop/cover/layers_panel.py`
- Create: `desktop/tests/test_cover_page.py`

**Interfaces:**
- Cover setup requires source, trim size, confirmed page count, paper preset/caliper, bleed, and optional spine override.
- Inspector edits exact X/Y/W/H, rotation, opacity, and type-specific content.
- Layer panel changes selection, z-order, visibility, and deletion.

- [ ] **Step 1: Write failing setup and inspector tests**

```python
def test_page_count_must_be_confirmed_before_editor(qtbot, epub_path):
    page = CoverPage()
    qtbot.addWidget(page)
    page.setup_panel.set_source(epub_path)
    page.setup_panel.page_count_spin.setValue(160)
    page.setup_panel.page_count_confirmed.setChecked(False)
    assert not page.setup_panel.create_button.isEnabled()


def test_inspector_emits_exact_mm_patch(qtbot, text_element):
    inspector = ElementInspector()
    qtbot.addWidget(inspector)
    inspector.set_element(text_element)
    with qtbot.waitSignal(inspector.patch_requested) as signal:
        inspector.x_spin.setValue(12.75)
        inspector.x_spin.editingFinished.emit()
    assert signal.args == [text_element.id, {"transform": {"x_mm": 12.75}}]
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_page.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Build the setup panel**

Controls:

- source picker for `.epub`, `.docx`, `.pdf`;
- trim presets A5, A6, 4×6;
- page count integer and `我已確認頁數` checkbox;
- paper presets 70/80/100/120 gsm;
- custom caliper `0.01..1.00 mm`;
- automatic spine display;
- optional manual spine override;
- bleed `0..10 mm`;
- image mode front-only/full-spread;
- template selector.

When metadata inspection returns an estimate, display `估算頁數` and leave confirmation unchecked. Conversion payloads set actual page count and confirmation checked.

```python
class CoverSetupPanel(QWidget):
    create_requested = Signal(CoverSetupValues)

    def __init__(self) -> None:
        super().__init__()
        self.page_count = QSpinBox()
        self.page_count.setRange(1, 1_000_000)
        self.page_confirmed = QCheckBox("我已確認頁數")
        self.trim = QComboBox()
        self.trim.addItem("A5", (148.0, 210.0))
        self.trim.addItem("A6", (105.0, 148.0))
        self.trim.addItem("4×6 英吋", (101.6, 152.4))
        self.paper = QComboBox()
        for label, caliper in (("70 gsm", 0.09), ("80 gsm", 0.10), ("100 gsm", 0.12), ("120 gsm", 0.14)):
            self.paper.addItem(label, caliper)
        self.caliper = QDoubleSpinBox()
        self.caliper.setRange(0.01, 1.00)
        self.caliper.setDecimals(3)
        self.bleed = QDoubleSpinBox()
        self.bleed.setRange(0.0, 10.0)
        self.bleed.setValue(3.0)

    def load_inspection(self, inspection: dict[str, object]) -> None:
        count = inspection.get("page_count")
        if count is not None:
            self.page_count.setValue(int(count))
        estimated = bool(inspection.get("page_count_estimated", False))
        self.page_confirmed.setChecked(False)
        self.page_count.setSuffix("（估算頁數）" if estimated else "")

    def values(self) -> CoverSetupValues:
        if not self.page_confirmed.isChecked():
            raise ValueError("請確認正文頁數。")
        return CoverSetupValues(
            trim_size_mm=self.trim.currentData(),
            page_count=self.page_count.value(),
            paper_caliper_mm=self.caliper.value(),
            bleed_mm=self.bleed.value(),
        )
```

- [ ] **Step 4: Build the editor workspace**

Use a three-column splitter:

```text
left: templates, add image/text, layers
center: canvas and zoom controls
right: metadata, geometry, element inspector, export
```

Connect controller, canvas, inspector, and layer panel only through typed signals.

```python
class CoverPage(QWidget):
    def __init__(self, controller: CoverController) -> None:
        super().__init__()
        self.controller = controller
        self.templates = TemplatePanel()
        self.assets = AssetsPanel()
        self.layers = LayersPanel()
        self.canvas = CoverCanvas()
        self.inspector = ElementInspector()
        self.setup = CoverSetupPanel()
        self.export_panel = ExportPanel()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.templates)
        left_layout.addWidget(self.assets)
        left_layout.addWidget(self.layers)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(self.canvas)
        center_layout.addWidget(self.canvas.zoom_controls)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.setup)
        right_layout.addWidget(self.inspector)
        right_layout.addWidget(self.export_panel)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        QVBoxLayout(self).addWidget(splitter)

        self.templates.template_selected.connect(controller.apply_template)
        self.assets.image_imported.connect(controller.add_local_image)
        self.layers.selection_changed.connect(self.canvas.select_element)
        self.canvas.transform_committed.connect(controller.patch_element)
        self.canvas.selection_changed.connect(self.inspector.set_element)
        self.inspector.patch_requested.connect(controller.patch_element)
        self.controller.project_changed.connect(self.canvas.set_project)
        self.controller.project_changed.connect(self.layers.set_project)
        self.controller.preview_ready.connect(self.canvas.set_preview)
        self.export_panel.export_requested.connect(controller.export)
```

- [ ] **Step 5: Add image/text editing controls**

Image inspector: replace file, fit contain/cover, crop offsets, horizontal/vertical flip, blur, brightness, dark overlay, opacity.

Text inspector: text, font family/path, font size, weight, color, alignment, line spacing, direction, X/Y/W/H, rotation, opacity.

```python
class ElementInspector(QWidget):
    patch_requested = Signal(str, dict)

    def apply_common(self, element_id: str) -> None:
        self.patch_requested.emit(element_id, {
            "transform": {
                "x_mm": self.x_mm.value(),
                "y_mm": self.y_mm.value(),
                "width_mm": self.width_mm.value(),
                "height_mm": self.height_mm.value(),
                "rotation_deg": self.rotation.value(),
            },
            "opacity": self.opacity.value() / 100.0,
        })

    def apply_text(self, element_id: str) -> None:
        self.patch_requested.emit(element_id, {
            "content": {
                "text": self.text.toPlainText(),
                "font_family": self.font_family.currentText(),
                "font_path": self.font_path.text() or None,
                "font_size_pt": self.font_size.value(),
                "font_weight": self.font_weight.value(),
                "color": self.color.name(),
                "align": self.alignment.currentData(),
                "line_spacing": self.line_spacing.value(),
                "direction": self.direction.currentData(),
            }
        })
```

- [ ] **Step 6: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_page.py -q
git add python/src/epub_a4_word_desktop/pages/cover_page.py \
  python/src/epub_a4_word_desktop/cover desktop/tests/test_cover_page.py
git commit -m "feat: add desktop cover setup and inspector workspace"
```

Expected: PASS.

---
