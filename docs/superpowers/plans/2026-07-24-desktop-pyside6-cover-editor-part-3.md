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

## Part 3: Tasks 8–10

### Task 8: Add local/embedded artwork selection and crop interaction

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/assets_panel.py`
- Create: `python/src/epub_a4_word_desktop/cover/crop_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Create: `desktop/tests/test_assets_panel.py`
- Create: `desktop/tests/test_crop_dialog.py`

**Interfaces:**
- Produces asset sources: EPUB embedded images and local files.
- Accepts PNG, JPEG, GIF first frame, WebP, and SVG only when the shared core can decode it.
- Crop dialog emits normalized crop rectangle values in `0..1`.

- [ ] **Step 1: Write failing asset-selection tests**

```python
def test_embedded_cover_selection_extracts_to_working_dir(qtbot, controller, embedded_asset):
    panel = AssetsPanel(controller)
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.asset_selected) as signal:
        panel.select_embedded_asset(embedded_asset["id"])
    assert Path(signal.args[0]).parent.name == "assets"


def test_crop_rect_is_normalized(qtbot, source_png):
    dialog = CropDialog(source_png, QRectF(0.1, 0.2, 0.7, 0.6))
    qtbot.addWidget(dialog)
    result = dialog.crop_rect()
    assert 0 <= result.x() <= 1
    assert 0 <= result.y() <= 1
    assert result.right() <= 1
    assert result.bottom() <= 1
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_assets_panel.py desktop/tests/test_crop_dialog.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement embedded extraction and local copy**

Never edit the source file. Copy every selected image to `<working_dir>/assets/<sha256-prefix>-<safe-name>` and return that absolute path. Reject files larger than `50 MiB` or decoded dimensions above `20000 × 20000` pixels.

```python
MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000


def import_local_asset(source: Path, working_dir: Path) -> Path:
    size = source.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError("圖片超過 50 MiB。")
    with Image.open(source) as image:
        image.verify()
        width, height = image.size
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError("圖片像素尺寸超過 20000 × 20000。")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", source.name).strip("._") or "image"
    assets = working_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    destination = assets / f"{digest}-{safe}"
    shutil.copyfile(source, destination)
    return destination.resolve()
```

- [ ] **Step 4: Implement crop dialog**

The dialog displays the source image, aspect-ratio overlay for the selected element, draggable crop rectangle, reset button, and live percentage fields. Store:

```json
{"crop_left":0.1,"crop_top":0.2,"crop_right":0.2,"crop_bottom":0.2}
```

Values represent fractions removed from each side and must leave positive width/height.

- [ ] **Step 5: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_assets_panel.py desktop/tests/test_crop_dialog.py -q
git add python/src/epub_a4_word_desktop/cover \
  python/src/epub_a4_word_desktop/pages/cover_page.py desktop/tests
git commit -m "feat: add desktop cover asset and crop tools"
```

Expected: PASS.

---

### Task 9: Add project save/open and independent PDF/DOCX export

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/project_files.py`
- Create: `python/src/epub_a4_word_desktop/cover/export_worker.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Create: `desktop/tests/test_project_files.py`
- Create: `desktop/tests/test_export_worker.py`

**Interfaces:**
- Project file suffix: `.cover.json`.
- `save_project_bundle(project_json, destination)` copies referenced local assets into a sibling `<stem>_assets` directory and rewrites paths relative to the project file.
- `open_project_bundle(path)` resolves asset paths to absolute paths and validates schema.
- Export creates both PDF and DOCX in a user-selected directory.

- [ ] **Step 1: Write failing project portability tests**

```python
def test_saved_project_uses_relative_asset_paths(project_json, tmp_path):
    path = save_project_bundle(project_json, tmp_path / "book.cover.json")
    raw = json.loads(path.read_text("utf-8"))
    image_path = next(e["content"]["path"] for e in raw["elements"] if e["kind"] == "image")
    assert not Path(image_path).is_absolute()
    assert (tmp_path / image_path).is_file()


def test_export_creates_independent_named_files(controller, tmp_path):
    result = run_export(controller.project_json, tmp_path, dpi=300)
    assert Path(result["pdf"]["path"]).name == "範例書_完整書封.pdf"
    assert Path(result["docx"]["path"]).name == "範例書_完整書封.docx"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_project_files.py desktop/tests/test_export_worker.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement project bundle save/open**

Use atomic writes:

```python
temporary = destination.with_suffix(destination.suffix + ".tmp")
temporary.write_text(rewritten_json, encoding="utf-8")
temporary.replace(destination)
```

Deduplicate copied images by SHA-256. Missing assets abort save/open with an error listing the exact path.

- [ ] **Step 4: Implement background export**

`ExportWorker` calls shared `export_cover`; signals progress stages `準備`, `輸出 PDF`, `輸出 DOCX`, `完成`. Disable editor mutations during export but leave zoom and scroll enabled. On error, preserve any previously existing output files by exporting to temporary names and replacing only after both outputs validate.

```python
class ExportWorker(QRunnable):
    def __init__(self, project_json: str, pdf: Path, docx: Path, dpi: int) -> None:
        super().__init__()
        self.project_json = project_json
        self.pdf = pdf
        self.docx = docx
        self.dpi = dpi
        self.signals = ExportSignals()

    def run(self) -> None:
        temporary_dir = Path(tempfile.mkdtemp(prefix="epub2a4-export-"))
        temp_pdf = temporary_dir / self.pdf.name
        temp_docx = temporary_dir / self.docx.name
        try:
            self.signals.progress.emit("準備")
            result = export_cover(
                self.project_json,
                str(temp_pdf),
                str(temp_docx),
                self.dpi,
            )
            self.signals.progress.emit("輸出 PDF")
            validate_pdf(temp_pdf)
            self.signals.progress.emit("輸出 DOCX")
            validate_docx(temp_docx)
            os.replace(temp_pdf, self.pdf)
            os.replace(temp_docx, self.docx)
            self.signals.progress.emit("完成")
            self.signals.completed.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            shutil.rmtree(temporary_dir, ignore_errors=True)
```

- [ ] **Step 5: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_project_files.py desktop/tests/test_export_worker.py -q
git add python/src/epub_a4_word_desktop/cover \
  python/src/epub_a4_word_desktop/pages/cover_page.py desktop/tests
git commit -m "feat: save desktop cover projects and export both formats"
```

Expected: PASS.

---

### Task 10: Complete desktop smoke tests and migration documentation

**Files:**
- Create: `desktop/tests/test_desktop_smoke.py`
- Create: `scripts/desktop_smoke.py`
- Modify: `README.md`
- Create: `CHANGELOG.md`
- Modify: `BUILD_STATUS.md`

**Interfaces:**
- Smoke script opens the main window offscreen, navigates through converter and cover pages, loads a fixture project, renders preview, and exports to a temporary directory.

- [ ] **Step 1: Add the complete smoke test**

```python
def test_desktop_cover_smoke(qtbot, cover_fixture, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigate(AppRoute.COVER)
    cover_page = window.pages[AppRoute.COVER]
    cover_page.controller.replace_project(cover_fixture, clear_history=True)
    cover_page.controller.render_preview_now()
    qtbot.waitUntil(lambda: cover_page.canvas.has_preview, timeout=10000)
    result = run_export(cover_fixture, tmp_path, dpi=200)
    assert Path(result["pdf"]["path"]).is_file()
    assert Path(result["docx"]["path"]).is_file()
```

- [ ] **Step 2: Run the full desktop test gate**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests -q
PYTHONPATH=python/src python3.13 scripts/desktop_smoke.py --offscreen
```

Expected: zero failures and `desktop smoke: PASS`.

- [ ] **Step 3: Manually verify default and legacy startup**

```bash
python3.13 -m epub_a4_word_desktop
python3.13 -m epub_a4_word_desktop --legacy-gui
```

Expected: PySide6 starts by default; Tkinter starts only with the flag.

- [ ] **Step 4: Update documentation**

Document desktop requirements, local/embedded artwork flow, project save/open, independent export, shortcut keys, known DOCX compatibility limits, and that online search arrives only after the search plan is implemented.

Add these exact README headings and verification commands:

```markdown
## 電腦版 PySide6

- Windows、macOS、Linux 使用相同 PySide6 介面。
- `epub2a4-desktop --legacy-gui` 暫時開啟舊 Tkinter 介面。
- 封面工具可使用 EPUB 內建圖片或本機圖片；此階段尚未啟用網路搜尋。
- 封面 PDF 與 DOCX 獨立輸出，不修改正文。

### 封面專案

使用「儲存專案」建立 JSON 與 `assets/` 資料夾；重新開啟時，相對資產路徑會以專案所在目錄解析。

### 快捷鍵

- Ctrl+Z：復原
- Ctrl+Shift+Z：重做
- Ctrl+0：符合視窗
- Ctrl+1：100%

### DOCX 相容性

PDF 是列印基準。Word 與 LibreOffice 對部分浮動文字框的呈現可能略有差異。
```

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests -q
QT_QPA_PLATFORM=offscreen python3.13 scripts/desktop_smoke.py
```

- [ ] **Step 5: Commit**

```bash
git add desktop/tests/test_desktop_smoke.py scripts/desktop_smoke.py \
  README.md CHANGELOG.md BUILD_STATUS.md
git commit -m "test: add PySide6 desktop acceptance gate"
```
