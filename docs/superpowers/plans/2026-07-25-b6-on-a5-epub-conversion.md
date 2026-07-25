# B6 Content on A5 EPUB Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an EPUB-only conversion mode that semantically reflows editable book content into a centered Japanese B6 trim rectangle of 128 × 182 mm while keeping each Word page physically A5 at 148 × 210 mm, with optional crop marks.

**Architecture:** Extend the current imposition and pagination settings with a single-page `b6_on_a5` mode, asymmetric physical page margins, and an output-mark mode. The existing EPUB parser and paginator continue to own semantic reflow; the DOCX writer receives resolved A5/B6 geometry and optionally adds eight floating crop-mark lines outside the B6 rectangle. The PySide6 converter exposes the new mode, mark choice, and a fixed informational preview.

**Tech Stack:** Python 3.13, python-docx 1.1.2, lxml/OOXML, PySide6 6.11, pytest/pytest-qt, PyInstaller 6.

## Global Constraints

- Input for this mode is EPUB only.
- Physical Word page size is A5: 148 × 210 mm.
- Trim rectangle is Japanese B6: 128 × 182 mm.
- The B6 rectangle is centered, producing 10 mm left/right and 14 mm top/bottom physical margins.
- EPUB content is semantically reflowed; do not rasterize pages and do not crop existing A5 page images.
- Text remains editable and rewraps to the resolved B6-area typography width.
- Images scale proportionally to fit inside the B6 page area and must not be clipped at the trim boundary.
- Existing quarter-A4, signature, A5, and 4×6 behavior remains unchanged.
- Output mark choices are `普通列印` and `附裁切標記`; normal is the default.
- Crop marks stay outside the B6 rectangle and never cross body text, images, or page numbers.
- Development runs only focused geometry/writer/UI tests, one desktop startup smoke check, and one final Windows portable build.

---

## File Structure

- `python/src/epub_a4_word/imposition.py`: adds `b6_on_a5` as a single-page imposition.
- `python/src/epub_a4_word/pagination.py`: resolves exact A5 paper, centered B6 cell, asymmetric page margins, and internal typography dimensions.
- `python/src/epub_a4_word/crop_marks.py`: creates/removes crop-mark VML lines in a header without entering the content rectangle.
- `python/src/epub_a4_word/docx_writer.py`: writes asymmetric section margins and optional crop marks.
- `python/src/epub_a4_word/converter.py`: progress labels and result mode support.
- `python/src/epub_a4_word_desktop/conversion/models.py`: request validation, mark mode, and B6 trim handoff.
- `python/src/epub_a4_word_desktop/pages/converter_page.py`: new mode, mark selector, and preview.
- `python/src/epub_a4_word_desktop/conversion/layout_preview.py`: draws A5 paper, B6 trim rectangle, and optional marks.
- `python/src/epub_a4_word/cover/service.py` and desktop cover setup: allow B6 cover dimensions after conversion.

---

### Task 1: Add the EPUB-Only B6-on-A5 Mode and Request Contract

**Files:**
- Modify: `python/src/epub_a4_word/imposition.py`
- Modify: `python/src/epub_a4_word/pagination.py`
- Modify: `python/src/epub_a4_word/converter.py`
- Modify: `python/src/epub_a4_word_desktop/conversion/legacy_adapter.py`
- Modify: `python/src/epub_a4_word_desktop/conversion/models.py`
- Create: `python-tests/test_b6_on_a5_mode.py`

**Interfaces:**
- Extends `ImpositionMode` with `"b6_on_a5"`.
- Adds `OutputMarkMode = Literal["normal", "crop_marks"]`.
- Adds `LayoutSettings.output_mark_mode: OutputMarkMode = "normal"`.
- Adds `ConversionRequest.output_mark_mode: str = "normal"`.
- `trim_size_for_mode("b6_on_a5") -> (128.0, 182.0)`.

- [ ] **Step 1: Add one focused mode-contract test**

```python
from pathlib import Path

import pytest

from epub_a4_word.imposition import build_imposition
from epub_a4_word_desktop.conversion.legacy_adapter import allowed_modes_for_path
from epub_a4_word_desktop.conversion.models import ConversionRequest, trim_size_for_mode


def test_b6_on_a5_is_epub_only_single_page_mode(tmp_path):
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"placeholder")
    assert "b6_on_a5" in allowed_modes_for_path(epub)
    assert "b6_on_a5" not in allowed_modes_for_path(Path("book.docx"))
    assert build_imposition(3, "b6_on_a5").sides == ((1,), (2,), (3,))
    assert trim_size_for_mode("b6_on_a5") == (128.0, 182.0)

    request = ConversionRequest(
        input_path=epub,
        output_path=tmp_path / "book.docx",
        imposition_mode="b6_on_a5",
        output_mark_mode="crop_marks",
    )
    request.validate()
```

- [ ] **Step 2: Run the focused test and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/test_b6_on_a5_mode.py -q
```

Expected: FAIL because the mode and request field do not exist.

- [ ] **Step 3: Extend the imposition types and builder**

Change:

```python
ImpositionMode = Literal[
    "four_up",
    "signature16",
    "single_a5",
    "single_4x6",
    "b6_on_a5",
]
```

Treat `b6_on_a5` through `_build_single_page`.

- [ ] **Step 4: Add output-mark configuration**

In `pagination.py`:

```python
OutputMarkMode = Literal["normal", "crop_marks"]

@dataclass(frozen=True)
class LayoutSettings:
    # existing fields remain unchanged
    output_mark_mode: OutputMarkMode = "normal"
    page_margin_left_cm: float | None = None
    page_margin_right_cm: float | None = None
    page_margin_top_cm: float | None = None
    page_margin_bottom_cm: float | None = None
```

In `ConversionRequest`, add `output_mark_mode: str = "normal"`, validate membership in `{"normal", "crop_marks"}`, and pass it to `LayoutSettings`.

- [ ] **Step 5: Restrict the mode to EPUB and add labels**

`allowed_modes_for_path(.epub)` returns the existing modes plus `b6_on_a5`; DOCX modes remain unchanged. Add converter progress label `B6 內容頁（A5 紙張）`.

- [ ] **Step 6: Add B6 trim handoff**

Extend `_TRIM_SIZE_BY_MODE` with:

```python
"b6_on_a5": (128.0, 182.0),
```

- [ ] **Step 7: Run the focused test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/test_b6_on_a5_mode.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add python/src/epub_a4_word/imposition.py python/src/epub_a4_word/pagination.py python/src/epub_a4_word/converter.py python/src/epub_a4_word_desktop/conversion python-tests/test_b6_on_a5_mode.py
git commit -m "feat: add EPUB B6-on-A5 conversion mode"
```

---

### Task 2: Resolve Exact A5 Paper and Centered B6 Geometry

**Files:**
- Modify: `python/src/epub_a4_word/pagination.py`
- Create: `python-tests/test_b6_on_a5_geometry.py`

**Interfaces:**
- `resolve_layout(LayoutSettings(imposition_mode="b6_on_a5"))` returns exact paper, margins, cell, and content dimensions.
- Existing modes continue deriving symmetric margins from `outer_margin_cm`.

- [ ] **Step 1: Add one exact-geometry test**

```python
import pytest

from epub_a4_word.pagination import LayoutSettings, resolve_layout


def test_b6_on_a5_geometry_is_centered_and_uses_internal_book_margins():
    resolved = resolve_layout(
        LayoutSettings(imposition_mode="b6_on_a5", margin_mode="safe")
    )
    assert resolved.paper_width_cm == pytest.approx(14.8)
    assert resolved.paper_height_cm == pytest.approx(21.0)
    assert resolved.page_margin_left_cm == pytest.approx(1.0)
    assert resolved.page_margin_right_cm == pytest.approx(1.0)
    assert resolved.page_margin_top_cm == pytest.approx(1.4)
    assert resolved.page_margin_bottom_cm == pytest.approx(1.4)
    assert resolved.cell_width_cm == pytest.approx(12.8)
    assert resolved.cell_height_cm == pytest.approx(18.2)
    assert resolved.grid_rows == 1
    assert resolved.grid_cols == 1
    assert resolved.page_prefix_height_cm == pytest.approx(0.0)
    assert resolved.content_width_pt < 12.8 * 72 / 2.54
    assert resolved.content_height_pt < 18.2 * 72 / 2.54
```

- [ ] **Step 2: Run and verify the geometry is not yet resolved**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/test_b6_on_a5_geometry.py -q
```

Expected: FAIL on unsupported mode or incorrect dimensions.

- [ ] **Step 3: Add exact constants**

```python
B6_WIDTH_CM = 12.8
B6_HEIGHT_CM = 18.2
B6_ON_A5_HORIZONTAL_MARGIN_CM = 1.0
B6_ON_A5_VERTICAL_MARGIN_CM = 1.4
```

- [ ] **Step 4: Resolve B6-on-A5 before generic symmetric calculations**

For `b6_on_a5`, set:

```python
paper_width = A5_WIDTH_CM
paper_height = A5_HEIGHT_CM
grid_rows = 1
grid_cols = 1
prefix_height = 0.0
page_left = page_right = B6_ON_A5_HORIZONTAL_MARGIN_CM
page_top = page_bottom = B6_ON_A5_VERTICAL_MARGIN_CM
cell_width = B6_WIDTH_CM
cell_height = B6_HEIGHT_CM
```

Then calculate `content_width_pt` and `content_height_pt` using the existing margin preset as margins inside the B6 cell. Keep footer and pagination safety deductions inside the B6 height.

- [ ] **Step 5: Preserve legacy behavior**

For all other modes, resolve `page_margin_left_cm`, `page_margin_right_cm`, `page_margin_top_cm`, and `page_margin_bottom_cm` to the existing `outer_margin_cm` value. Do not alter their cell sizes, prefix heights, or internal margins.

- [ ] **Step 6: Run the focused geometry test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/test_b6_on_a5_geometry.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word/pagination.py python-tests/test_b6_on_a5_geometry.py
git commit -m "feat: resolve centered B6 geometry on A5 paper"
```

---

### Task 3: Write A5 DOCX Pages with Optional External Crop Marks

**Files:**
- Create: `python/src/epub_a4_word/crop_marks.py`
- Modify: `python/src/epub_a4_word/docx_writer.py`
- Create: `python-tests/test_b6_on_a5_docx.py`

**Interfaces:**
- Produces `CropMarkFrame(page_width_cm, page_height_cm, left_cm, top_cm, width_cm, height_cm)`.
- Produces `add_crop_marks(section, frame, length_mm=5.0, gap_mm=2.0) -> None`.
- `write_docx` applies marks only for `b6_on_a5` plus `output_mark_mode == "crop_marks"`.

- [ ] **Step 1: Add one DOCX OOXML test for both mark modes**

```python
from zipfile import ZipFile

from docx import Document


def test_b6_crop_mark_mode_adds_eight_lines_outside_content(tmp_path, one_page, resources):
    normal = tmp_path / "normal.docx"
    marked = tmp_path / "marked.docx"
    write_fixture_docx(normal, one_page, resources, output_mark_mode="normal")
    write_fixture_docx(marked, one_page, resources, output_mark_mode="crop_marks")

    normal_doc = Document(normal)
    marked_doc = Document(marked)
    assert normal_doc.sections[0].page_width.mm == pytest.approx(148.0, abs=0.2)
    assert marked_doc.sections[0].page_height.mm == pytest.approx(210.0, abs=0.2)

    with ZipFile(normal) as archive:
        normal_headers = b"".join(archive.read(name) for name in archive.namelist() if name.startswith("word/header"))
    with ZipFile(marked) as archive:
        marked_headers = b"".join(archive.read(name) for name in archive.namelist() if name.startswith("word/header"))
    assert normal_headers.count(b"<v:line") == 0
    assert marked_headers.count(b"<v:line") == 8
```

- [ ] **Step 2: Run and verify crop-mark support is absent**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/test_b6_on_a5_docx.py -q
```

Expected: FAIL because crop-mark XML is not written.

- [ ] **Step 3: Apply asymmetric section margins**

Replace the four uses of `settings.outer_margin_cm` for Word section margins with the resolved fields:

```python
section.left_margin = Cm(settings.page_margin_left_cm)
section.right_margin = Cm(settings.page_margin_right_cm)
section.top_margin = Cm(settings.page_margin_top_cm)
section.bottom_margin = Cm(settings.page_margin_bottom_cm)
```

Keep the table width at `cell_width_cm * grid_cols` and row height at `cell_height_cm`.

- [ ] **Step 4: Implement eight crop-mark segments**

Use a B6 frame with left 10 mm, top 14 mm, right 138 mm, and bottom 196 mm. Each corner gets one horizontal and one vertical line. Each line is 5 mm long with a 2 mm gap from the trim corner, so every line remains inside the A5 outer margin.

Create VML lines in the first section header:

```python
def _append_vml_line(paragraph, *, x1_pt: float, y1_pt: float, x2_pt: float, y2_pt: float) -> None:
    pict = OxmlElement("w:pict")
    line = OxmlElement("v:line")
    line.set("from", "0,0")
    line.set("to", "21600,21600")
    line.set("strokecolor", "#000000")
    line.set("strokeweight", "0.5pt")
    line.set(
        "style",
        (
            f"position:absolute;left:{x1_pt:.3f}pt;top:{y1_pt:.3f}pt;"
            f"width:{x2_pt - x1_pt:.3f}pt;height:{y2_pt - y1_pt:.3f}pt;"
            "mso-position-horizontal-relative:page;"
            "mso-position-vertical-relative:page;z-index:251659264"
        ),
    )
    pict.append(line)
    paragraph._p.append(pict)
```

For negative width or height segments, normalize the starting coordinate and use the appropriate VML `from`/`to` direction so the line still points to the trim corner. Set header distance to zero and remove header paragraph spacing.

- [ ] **Step 5: Call crop-mark writer only for the selected mode**

```python
if (
    settings.imposition_mode == "b6_on_a5"
    and settings.output_mark_mode == "crop_marks"
):
    add_crop_marks(
        section,
        CropMarkFrame(14.8, 21.0, 1.0, 1.4, 12.8, 18.2),
    )
```

Normal mode must not create a header part solely for marks.

- [ ] **Step 6: Run the focused DOCX test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/test_b6_on_a5_docx.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word/crop_marks.py python/src/epub_a4_word/docx_writer.py python-tests/test_b6_on_a5_docx.py
git commit -m "feat: add optional B6 crop marks to A5 DOCX"
```

---

### Task 4: Add Converter Controls and Fixed A5/B6 Preview

**Files:**
- Create: `python/src/epub_a4_word_desktop/conversion/layout_preview.py`
- Modify: `python/src/epub_a4_word_desktop/pages/converter_page.py`
- Create: `desktop/tests/test_b6_converter_page.py`

**Interfaces:**
- Produces `B6OnA5Preview.set_mark_mode(mode: str)`.
- Converter mode value is `b6_on_a5` with label `B6 內容置於 A5 紙張`.
- Mark combo data values are `normal` and `crop_marks`.

- [ ] **Step 1: Add one focused UI behavior test**

```python
def test_b6_mode_shows_mark_choice_and_builds_request(qtbot, tmp_path):
    source = tmp_path / "book.epub"
    source.write_bytes(b"placeholder")
    page = ConverterPage()
    qtbot.addWidget(page)
    page.set_source_path(source)
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("b6_on_a5"))
    assert page.output_mark_combo.isVisible()
    assert page.layout_preview.isVisible()
    page.output_mark_combo.setCurrentIndex(page.output_mark_combo.findData("crop_marks"))
    request = page._build_request()
    assert request.imposition_mode == "b6_on_a5"
    assert request.output_mark_mode == "crop_marks"
```

- [ ] **Step 2: Run and verify the controls are absent**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_b6_converter_page.py -q
```

Expected: FAIL because the combo and preview do not exist.

- [ ] **Step 3: Add mode and mark labels**

Extend `_MODE_LABELS`:

```python
"b6_on_a5": "B6 內容置於 A5 紙張",
```

Create a combo containing:

```python
("普通列印", "normal")
("附裁切標記", "crop_marks")
```

Default to `normal`.

- [ ] **Step 4: Implement the preview widget**

`B6OnA5Preview.paintEvent` draws:

- a white A5 rectangle with 148:210 aspect ratio;
- a centered B6 rectangle with 128:182 aspect ratio;
- light labels `A5 紙張` and `B6 128 × 182 mm`;
- eight short marks only in `crop_marks` mode.

Use `QPainter` and the widget palette; do not hard-code a theme-specific background. The preview is informational and has no mouse handlers.

- [ ] **Step 5: Toggle B6-specific controls**

Connect `mode_combo.currentIndexChanged`. In B6 mode:

- show mark combo and preview;
- hide the existing generic `顯示裁切／折線` checkbox because it applies to multi-up layouts;
- retain margin mode because it controls typography margins inside the B6 trim.

Outside B6 mode, hide the mark combo/preview and restore the existing cut-guide checkbox.

- [ ] **Step 6: Build the request**

Pass `output_mark_mode` from the combo only in B6 mode; pass `normal` otherwise. Preserve all current fields.

- [ ] **Step 7: Run the focused UI test**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_b6_converter_page.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add python/src/epub_a4_word_desktop/conversion/layout_preview.py python/src/epub_a4_word_desktop/pages/converter_page.py desktop/tests/test_b6_converter_page.py
git commit -m "feat: add B6-on-A5 converter controls and preview"
```

---

### Task 5: Support B6 Cover Handoff After Conversion

**Files:**
- Modify: `python/src/epub_a4_word/cover/service.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Modify: `desktop/tests/test_cover_page.py`

**Interfaces:**
- Cover trim preset `B6` maps to `(128.0, 182.0)`.
- Existing `ConversionCompletion.to_cover_payload()` passes B6 dimensions unchanged.

- [ ] **Step 1: Add one handoff test**

```python
def test_b6_conversion_payload_selects_b6_cover_trim(qtbot, cover_page, tmp_path):
    source = tmp_path / "book.epub"
    source.write_bytes(b"placeholder")
    cover_page.open_from_conversion(
        {
            "source_path": str(source),
            "page_count": 180,
            "trim_size_mm": {"width_mm": 128.0, "height_mm": 182.0},
        }
    )
    assert cover_page.setup_panel.trim_combo.currentText() == "B6"
```

- [ ] **Step 2: Run and verify B6 trim is rejected**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_page.py -q
```

Expected: FAIL with unsupported cover trim size.

- [ ] **Step 3: Add B6 to shared and desktop trim presets**

In shared cover service `_SUPPORTED_TRIMS`, add `(128.0, 182.0)`. Update the validation message to `裁切尺寸只支援 A5、B6、A6 或 4×6 英吋。`.

In `CoverSetupPanel.TRIM_PRESETS`, add:

```python
("B6", (128.0, 182.0)),
```

- [ ] **Step 4: Run the focused handoff test**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_page.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python/src/epub_a4_word/cover/service.py python/src/epub_a4_word_desktop/cover/setup_panel.py desktop/tests/test_cover_page.py
git commit -m "feat: support B6 cover handoff"
```

---

### Task 6: Focused Integration Check and Final Windows Portable Build

**Files:**
- Modify: `README.md`
- Modify: `BUILD_STATUS.md`
- Modify: `.github/workflows/windows-portable.yml`

**Interfaces:**
- Produces a Windows portable ZIP for manual Word and print validation.

- [ ] **Step 1: Run only the focused B6 checks**

```bash
PYTHONPATH=python/src QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  python-tests/test_b6_on_a5_mode.py \
  python-tests/test_b6_on_a5_geometry.py \
  python-tests/test_b6_on_a5_docx.py \
  desktop/tests/test_b6_converter_page.py -q
```

Expected: PASS.

- [ ] **Step 2: Run one desktop startup smoke check**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=python/src python3.13 -m epub_a4_word_desktop --portable-smoke-test
```

Expected: exit code 0.

- [ ] **Step 3: Update the Windows workflow without adding a broad matrix**

Add the four focused B6 tests to the existing Windows job before PyInstaller. Do not add macOS, Linux, Android, or live-network checks for this feature.

- [ ] **Step 4: Build the Windows portable package once**

Run the existing `Windows Portable` workflow and download the resulting ZIP and SHA-256 file.

- [ ] **Step 5: Document the mode accurately**

README instructions must state:

- source must be EPUB;
- Word paper remains A5;
- editable content is reflowed for B6 trim;
- normal mode has no marks;
- crop-mark mode places marks outside the B6 area;
- printing must use 100% / actual size rather than fit-to-page.

Do not claim printed accuracy before the user checks a physical print.

- [ ] **Step 6: Commit**

```bash
git add README.md BUILD_STATUS.md .github/workflows/windows-portable.yml
git commit -m "build: package B6-on-A5 EPUB conversion"
```

- [ ] **Step 7: Deliver for manual validation**

Ask the user to verify:

1. output opens in Microsoft Word;
2. paper size reports A5;
3. normal mode has no crop marks;
4. marked mode shows eight marks outside the B6 content;
5. text is editable and reflowed rather than rasterized;
6. large images fit without being cut off;
7. printing at actual size trims to 128 × 182 mm.
