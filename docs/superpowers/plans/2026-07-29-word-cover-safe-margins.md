# Word Cover Safe Margins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Microsoft Word from warning that exported cover DOCX margins are outside the printable area without moving or scaling cover content.

**Architecture:** Keep the existing page-relative absolute positioning for images, text boxes, shapes, and crop lines. Change only the four section page-margin declarations from zero to 12.7 mm; preserve page size, orientation, header/footer distances, gutter, and all print-plan geometry.

**Tech Stack:** Python 3.13, python-docx, OOXML, lxml, pytest

## Global Constraints

- Top, bottom, left, and right cover-DOCX margins are exactly `12.7 mm` (`720` twips).
- Header distance, footer distance, and gutter remain `0`.
- Paper size, orientation, section count, anchor coordinates, crop coordinates, and object sizes do not change.
- PDF, PNG, regular body-DOCX, and Android UI code remain untouched.
- Use test-driven development: observe the margin regression test fail before editing production code.

---

### Task 1: Emit Word-safe margins without changing cover geometry

**Files:**
- Modify: `python-tests/cover/test_docx_export.py:80-99`
- Modify: `python/src/epub_a4_word/cover/docx_export.py:8-11,71-103`

**Interfaces:**
- Consumes: `_configure_section(section, page: PrintPage) -> None`
- Produces: the same private interface, with `w:pgMar` page margins set to `720` twips and non-page margin fields left at `0`

- [ ] **Step 1: Change the real export test to require safe page margins**

Update `test_split_docx_has_two_exact_a4_sections` so its assertions distinguish the four printable page margins from the three fields that must remain zero:

```python
        for name in ("top", "right", "bottom", "left"):
            assert margins.get(f"{{{NS['w']}}}{name}") == "720"
        for name in ("header", "footer", "gutter"):
            assert margins.get(f"{{{NS['w']}}}{name}") == "0"
```

This catches the production bug where `_configure_section` writes zero to all seven fields. The expected `720` value is hand-derived from `12.7 / 25.4 * 1440`.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/cover/test_docx_export.py::test_split_docx_has_two_exact_a4_sections -q
```

Expected: FAIL because the four page-margin attributes contain `"0"` instead of `"720"`.

- [ ] **Step 3: Implement the minimal section-margin change**

Import `Mm`:

```python
from docx.shared import Mm
```

In `_configure_section`, assign a half-inch margin through python-docx while keeping the other section fields unchanged:

```python
    safe_margin = Mm(12.7)
    section.top_margin = safe_margin
    section.right_margin = safe_margin
    section.bottom_margin = safe_margin
    section.left_margin = safe_margin
    section.header_distance = 0
    section.footer_distance = 0
    section.gutter = 0
```

Write explicit OOXML values so serialization is deterministic:

```python
    safe_margin_twips = str(mm_to_twips(12.7))
    for name in ("top", "right", "bottom", "left"):
        page_margins.set(qn(f"w:{name}"), safe_margin_twips)
    for name in ("header", "footer", "gutter"):
        page_margins.set(qn(f"w:{name}"), "0")
```

Do not change `_to_page_rect`, print-plan rectangles, picture cropping, VML positioning, or crop-line generation.

- [ ] **Step 4: Run the focused DOCX export suite and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/cover/test_docx_export.py -q
```

Expected: all tests pass, including exact A4 sections, page-relative anchors, editable text, image cropping, and crop-frame lines.

- [ ] **Step 5: Commit the tested fix**

```powershell
git add python-tests/cover/test_docx_export.py python/src/epub_a4_word/cover/docx_export.py
git commit -m "fix: use Word-safe cover margins"
```

### Task 2: Verify all shared export consumers

**Files:**
- Verify only: `python-tests/cover/test_docx_export.py`
- Verify only: `python-tests/cover/test_golden_exports.py`
- Verify only: `python-tests/cover/test_modern_cover_reference.py`
- Verify only: `desktop/tests`

**Interfaces:**
- Consumes: `export_docx(project: CoverProject, output_path: Path | str) -> ExportResult`
- Produces: no new interface; provides integration evidence for Desktop and Android consumers of the shared Python exporter

- [ ] **Step 1: Run cover export integration tests**

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/cover/test_docx_export.py python-tests/cover/test_golden_exports.py python-tests/cover/test_modern_cover_reference.py -q
```

Expected: all tests pass and generated DOCX packages reopen successfully.

- [ ] **Step 2: Run the complete Python suite**

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests -q
```

Expected: all non-environment-skipped tests pass.

- [ ] **Step 3: Run the complete Desktop suite**

```powershell
.\.venv\Scripts\python.exe -m pytest desktop\tests -q
```

Expected: all tests pass.

- [ ] **Step 4: Run the Android unit suite against the shared exporter integration**

Set the existing local Android SDK path through `ANDROID_HOME` without creating or committing `local.properties`, then run:

```powershell
$env:ANDROID_HOME='C:\Users\fadai\AppData\Local\Android\Sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
& "$env:USERPROFILE\.gradle\wrapper\dists\gradle-9.1.0-bin\9agqghryom9wkf8r80qlhnts3\gradle-9.1.0\bin\gradle.bat" --no-daemon :app:testDebugUnitTest
```

Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 5: Verify repository scope**

```powershell
git diff --check
git status --short
git log -2 --oneline
```

Expected: no tracked modifications remain after the implementation commit; the pre-existing untracked `uv.lock` is not staged or committed.
