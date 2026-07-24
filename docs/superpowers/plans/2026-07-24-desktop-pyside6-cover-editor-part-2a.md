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

## Subpart A: Tasks 4–5

### Task 4: Migrate the existing conversion workflow to PySide6

**Files:**
- Create: `python/src/epub_a4_word_desktop/conversion/models.py`
- Create: `python/src/epub_a4_word_desktop/conversion/controller.py`
- Create: `python/src/epub_a4_word_desktop/pages/converter_page.py`
- Create: `desktop/tests/test_conversion_controller.py`
- Create: `desktop/tests/test_converter_page.py`

**Interfaces:**
- Produces: `ConversionController.start(request)` and signals `progress`, `completed`, `failed`, `cancelled`.
- Completed signal payload includes `source_path`, `output_path`, `page_count`, `trim_size_mm`, `title`, `author` for direct cover-tool entry.

- [ ] **Step 1: Add failing request validation tests**

```python
def test_docx_rejects_signature_mode(tmp_path):
    request = ConversionRequest(
        input_path=tmp_path / "input.docx",
        output_path=tmp_path / "output.docx",
        imposition_mode="signature16",
    )
    with pytest.raises(ValueError, match="DOCX"):
        request.validate()


def test_epub_completion_payload_uses_actual_page_count(conversion_result, request):
    payload = completion_payload(request, conversion_result)
    assert payload["page_count"] == conversion_result.mini_page_count
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_conversion_controller.py desktop/tests/test_converter_page.py -q
```

Expected: collection ERROR because the modules do not exist.

- [ ] **Step 3: Implement a cancellable worker**

Use `QRunnable` and a signal object:

```python
class ConversionWorker(QRunnable):
    def __init__(self, request: ConversionRequest, cancelled: threading.Event):
        super().__init__()
        self.request = request
        self.cancelled = cancelled
        self.signals = ConversionWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = convert_input(
                self.request.input_path,
                self.request.output_path,
                self.request.to_layout_settings(),
                self._progress,
            )
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.completed.emit(result)

    def _progress(self, percent: int, message: str) -> None:
        if self.cancelled.is_set():
            raise ConversionCancelled("轉換已取消。")
        self.signals.progress.emit(percent, message)
```

- [ ] **Step 4: Build the PySide6 conversion form**

The page must provide the same controls as the Android converter and the legacy GUI. Use `QFileDialog` for source/output, `QComboBox` for modes and margins, `QDoubleSpinBox` for sizes, `QCheckBox` for page numbers/guides, `QProgressBar`, and `QPlainTextEdit` for warnings.

On completion, show both:

- `儲存完成` with output path;
- `製作獨立書封` button emitting `open_cover_requested(payload)`.

```python
class ConverterPage(QWidget):
    open_cover_requested = Signal(dict)

    def __init__(self, controller: ConversionController) -> None:
        super().__init__()
        self.controller = controller
        self.source_edit = QLineEdit()
        self.mode_combo = QComboBox()
        self.margin_combo = QComboBox()
        self.body_size = QDoubleSpinBox()
        self.heading_size = QDoubleSpinBox()
        self.page_numbers = QCheckBox("顯示頁碼")
        self.cut_guides = QCheckBox("顯示裁切／折線")
        self.progress = QProgressBar()
        self.warnings = QPlainTextEdit()
        self.cover_button = QPushButton("製作獨立書封")
        self.cover_button.hide()
        self.cover_button.clicked.connect(self._emit_cover_payload)
        self.controller.completed.connect(self._on_completed)

    def _on_completed(self, result: ConversionCompletion) -> None:
        self._completion = result
        self.progress.setValue(100)
        self.warnings.setPlainText("\n".join(result.warnings))
        self.cover_button.setVisible(result.source.suffix.lower() == ".epub")
        QMessageBox.information(self, "儲存完成", str(result.output_path))

    def _emit_cover_payload(self) -> None:
        result = self._completion
        self.open_cover_requested.emit({
            "source_path": str(result.source),
            "page_count": result.actual_page_count,
            "trim_size_mm": {
                "width_mm": result.trim_size_mm[0],
                "height_mm": result.trim_size_mm[1],
            },
        })
```

- [ ] **Step 5: Run controller/page tests**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_conversion_controller.py desktop/tests/test_converter_page.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python/src/epub_a4_word_desktop/conversion \
  python/src/epub_a4_word_desktop/pages/converter_page.py desktop/tests
git commit -m "feat: migrate desktop conversion workflow to PySide6"
```

---

### Task 5: Implement the cover document controller and undoable commands

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/controller.py`
- Create: `python/src/epub_a4_word_desktop/cover/commands.py`
- Create: `python/src/epub_a4_word_desktop/cover/models.py`
- Create: `desktop/tests/test_cover_controller.py`

**Interfaces:**
- Produces: `CoverController.project_changed(str)`, `preview_ready(Path)`, `error(str)`.
- Produces methods `load_source`, `apply_template`, `replace_project`, `update_element`, `add_local_image`, `remove_element`, `undo`, `redo`.
- `QUndoStack` stores project mutations; export operations do not enter the undo stack.

- [ ] **Step 1: Write failing controller tests**

```python
def test_update_element_is_undoable(qtbot, project_json):
    controller = CoverController()
    controller.replace_project(project_json, clear_history=True)
    before = loads_project(controller.project_json)
    controller.update_element("front-title", {"transform": {"x_mm": 10.0}})
    assert loads_project(controller.project_json).elements_by_id["front-title"].transform.x_mm == 10.0
    controller.undo()
    assert loads_project(controller.project_json) == before


def test_local_image_is_copied_to_working_assets(tmp_path, project_json, source_png):
    controller = CoverController(working_dir=tmp_path)
    controller.replace_project(project_json, clear_history=True)
    element_id = controller.add_local_image(source_png, Region.FRONT)
    project = loads_project(controller.project_json)
    path = Path(project.elements_by_id[element_id].content["path"])
    assert path.parent == tmp_path / "assets"
    assert path.is_file()
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_controller.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement immutable project replacement commands**

Each undo command stores complete before/after JSON to avoid divergent partial update logic:

```python
class ReplaceProjectCommand(QUndoCommand):
    def __init__(self, controller, before_json: str, after_json: str, label: str):
        super().__init__(label)
        self.controller = controller
        self.before_json = before_json
        self.after_json = after_json

    def redo(self) -> None:
        self.controller._set_project_json(self.after_json)

    def undo(self) -> None:
        self.controller._set_project_json(self.before_json)
```

Use a pure `patch_element(project, element_id, patch) -> CoverProject` helper. Serialize the candidate as `candidate_json = dumps_project(candidate)` and validate it with `loads_project(candidate_json)` before pushing the command.

- [ ] **Step 4: Add debounced preview rendering**

Use a `QTimer` with `150 ms` single-shot debounce. Each project change schedules a worker which calls shared `render_preview`; attach a monotonically increasing generation ID and ignore stale worker results.

```python
class CoverController(QObject):
    preview_ready = Signal(Path)
    error = Signal(str)

    def __init__(self, service: CoverService, pool: QThreadPool) -> None:
        super().__init__()
        self.service = service
        self.pool = pool
        self._preview_generation = 0
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._start_preview)

    def schedule_preview(self) -> None:
        self._preview_generation += 1
        self._preview_timer.start()

    def _start_preview(self) -> None:
        generation = self._preview_generation
        worker = PreviewWorker(self.service, self.project_json, generation)
        worker.signals.completed.connect(self._accept_preview)
        worker.signals.failed.connect(self.error.emit)
        self.pool.start(worker)

    def _accept_preview(self, generation: int, path: Path) -> None:
        if generation == self._preview_generation:
            self.preview_ready.emit(path)
```

- [ ] **Step 5: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_controller.py -q
git add python/src/epub_a4_word_desktop/cover desktop/tests/test_cover_controller.py
git commit -m "feat: add desktop cover project controller"
```

Expected: PASS.

---
