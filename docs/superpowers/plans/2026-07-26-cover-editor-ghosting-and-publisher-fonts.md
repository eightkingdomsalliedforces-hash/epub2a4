# Cover Editor Ghosting and Publisher Fonts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicate cover images and graphics-item trails, then reproduce the supplied rounded publisher ISBN block consistently in the Qt editor and Pillow exports.

**Architecture:** Keep schema v1 and existing `CoverElement` content dictionaries. Add small pure helpers for typographic point conversion, font-role fallback selection and normalized barcode geometry; consume those helpers from both the desktop items and shared renderer. Change downloaded-image application from append semantics to region replacement semantics.

**Tech Stack:** Python 3.13, dataclasses, pathlib, Pillow, PySide6, pytest, pytest-qt.

## Global Constraints

- Do not generate, download or bundle font files or images.
- Keep proprietary DynaFont use optional and based only on fonts already installed on the user's computer.
- Preserve PDF, DOCX and preview rendering from the full project.
- Preserve schema-v1 compatibility.
- Use TDD: every production change follows a focused failing regression test.
- Keep PR #13 as draft until all platform checks pass.

---

### Task 1: Replace overlapping cover images by region

**Files:**
- Modify: `desktop/tests/test_cover_controller.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`

**Interfaces:**
- Consumes: `CoverController.add_downloaded_images(selections)` and `CoverController.add_composed_spread(source_path)`.
- Produces: `_without_replaced_cover_images(elements, replacement_regions)` and deterministic replacement behavior.

- [ ] **Step 1: Write failing tests**

Add tests that start with `source-cover-image` in `Region.FRONT`, apply a downloaded front selection, and assert that exactly one front/spread image remains and its path is the newly copied asset. Add a second test that applies a composed spread and asserts that all prior front, back, spine and spread image elements are removed before the new spread element is added.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
python -m pytest desktop/tests/test_cover_controller.py -k "replaces_existing or spread_replaces" -q
```

Expected: both tests fail because the current controller appends new images.

- [ ] **Step 3: Implement minimal replacement helper**

Add:

```python
@staticmethod
def _without_replaced_cover_images(
    elements: list[CoverElement], replacement_regions: set[Region]
) -> list[CoverElement]:
    replace_spread = Region.SPREAD in replacement_regions
    return [
        element
        for element in elements
        if not (
            element.kind is ElementKind.IMAGE
            and (
                replace_spread
                or element.region is Region.SPREAD
                or element.region in replacement_regions
            )
        )
    ]
```

Use it before adding downloaded panel selections and before adding a composed spread.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the same focused command and expect PASS.

- [ ] **Step 5: Commit**

Commit message: `fix: replace overlapping cover images`

---

### Task 2: Include selection controls in graphics invalidation bounds

**Files:**
- Modify: `desktop/tests/test_cover_canvas.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`

**Interfaces:**
- Produces: `CoverElementItem.contentRect() -> QRectF` and an expanded `boundingRect()`.
- Consumers: image, text and barcode paint methods and resize hit testing.

- [ ] **Step 1: Write failing bounds test**

Instantiate a 40 × 20 mm `CoverTextItem`. Assert `contentRect()` is exactly `QRectF(0, 0, 40, 20)` and `boundingRect()` extends at least half a handle on all four sides and at least `5 + half-handle` mm above the content for the rotation control.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python -m pytest desktop/tests/test_cover_canvas.py -k selection_controls -q
```

Expected: FAIL because `contentRect` does not exist and `boundingRect` equals the content box.

- [ ] **Step 3: Implement bounds separation**

Add `contentRect()` and make `boundingRect()` return `contentRect().adjusted(-half, -(5.0 + half), half, half)`. Update `_corner_at`, `_paint_selection_handles`, `CoverImageItem.paint`, `CoverBarcodeItem.paint` and `CoverTextItem.paint` to use `contentRect()` for content geometry.

- [ ] **Step 4: Run focused and canvas tests**

Run:

```bash
python -m pytest desktop/tests/test_cover_canvas.py desktop/tests/test_publisher_workflow.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `fix: repaint cover selection controls cleanly`

---

### Task 3: Add shared font roles and correct Qt point conversion

**Files:**
- Create: `python/src/epub_a4_word/cover/typography.py`
- Create: `python-tests/cover/test_typography.py`
- Modify: `desktop/tests/test_cover_canvas.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`

**Interfaces:**
- Produces:
  - `points_to_mm(points: object) -> float`
  - `font_candidates(role: str, requested: object = None) -> tuple[str, ...]`
  - roles `publisher_heading`, `publisher_details`, `ocr`, `default`.

- [ ] **Step 1: Write failing pure tests**

Assert `points_to_mm(24) == pytest.approx(8.4667)` and assert candidate ordering starts with DynaFont W5/W3 and OCR-B aliases for their respective roles.

- [ ] **Step 2: Write failing Qt font-size test**

Construct a 24 pt `CoverTextItem` and assert its internal font pixel size is approximately 8 scene units rather than 24. Expose a small `_font()` method for testability.

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```bash
python -m pytest python-tests/cover/test_typography.py desktop/tests/test_cover_canvas.py -k "typography or point_size" -q
```

Expected: FAIL because helpers and `_font()` do not exist.

- [ ] **Step 4: Implement typography helpers and Qt selection**

Use `QFontDatabase.families()` to select the first installed candidate. Set Qt font size using `setPixelSize(max(1, round(points_to_mm(font_size_pt))))`; the view transform then converts scene millimetres to screen pixels. Keep weight and fallback behavior.

- [ ] **Step 5: Run focused tests to verify GREEN**

Run the same focused command and expect PASS.

- [ ] **Step 6: Commit**

Commit message: `fix: use compact rounded publisher typography`

---

### Task 4: Resolve installed fonts for Pillow export

**Files:**
- Modify: `python/src/epub_a4_word/cover/fonts.py`
- Modify: `python-tests/cover/test_fonts.py`
- Modify: `python/src/epub_a4_word/cover/render.py`

**Interfaces:**
- Extends `resolve_font(font_family, font_path, size_px, fallback_families=())`.
- Uses `font_candidates()` from Task 3.

- [ ] **Step 1: Write failing font-discovery tests**

Create temporary fake font directory entries and monkeypatch the standard directory provider. Assert filename-normalized aliases such as `DFYuan-W3` and `OCR-B` select matching files before generic fallbacks. Assert explicit `font_path` remains highest priority.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
python -m pytest python-tests/cover/test_fonts.py -q
```

Expected: FAIL because family names are currently discarded.

- [ ] **Step 3: Implement cached local discovery**

Search Windows, macOS and Linux font directories recursively for `.ttf`, `.otf` and `.ttc` files. Normalize family/file hints to alphanumeric lowercase text and match against normalized filenames. Never download fonts. Fall back to `EPUB2A4_DEFAULT_FONT`, then Pillow's scalable default.

- [ ] **Step 4: Pass role fallbacks from text and barcode renderers**

For text, read `font_role` and pass `font_candidates(role, font_family)` to `resolve_font`. For barcode digits use the `ocr` role.

- [ ] **Step 5: Run font and render tests**

Run:

```bash
python -m pytest python-tests/cover/test_fonts.py python-tests/cover/test_render.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: resolve installed publisher fonts for export`

---

### Task 5: Rebuild the publisher block into separate weighted lines

**Files:**
- Modify: `python-tests/cover/test_publisher_back_template.py`
- Modify: `desktop/tests/test_publisher_workflow.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`

**Interfaces:**
- Produces template element IDs:
  - `back-isbn-label`
  - `back-isbn-code`
  - `back-publisher-heading`
  - `back-publisher-details`

- [ ] **Step 1: Write failing template assertions**

Assert the publisher name is a separate 7.5 pt element with `font_role=publisher_heading`, details are a 6.5 pt element with `font_role=publisher_details`, and the ISBN label is 7 pt with `font_role=ocr`. Assert `back-publisher-info` is no longer generated.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
python -m pytest python-tests/cover/test_publisher_back_template.py desktop/tests/test_publisher_workflow.py -q
```

Expected: FAIL because the current template emits one 8 pt publisher text block.

- [ ] **Step 3: Implement compact reference geometry**

Keep the left-top group fixed to the back safe area. Place the heading above the details at the right of the barcode. Omit either element when its data is empty; do not shift the barcode. Add the new IDs to `STANDARD_TEMPLATE_IDS` and keep old `back-publisher-info` there so applying the template cleans legacy content.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the same focused command and expect PASS.

- [ ] **Step 5: Commit**

Commit message: `fix: match rounded publisher information block`

---

### Task 6: Share accurate EAN and add-on text geometry

**Files:**
- Create: `python/src/epub_a4_word/cover/barcode_layout.py`
- Create: `python-tests/cover/test_barcode_layout.py`
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`

**Interfaces:**
- Produces `build_barcode_layout(isbn, addon) -> BarcodeLayout` with normalized module positions, ordinary/guard bar heights and text anchors.

- [ ] **Step 1: Write failing layout tests**

Assert EAN-13 splits text into first digit, left six and right six; five-digit add-on text is preserved and anchored above supplemental bars; main guards extend below ordinary bars.

- [ ] **Step 2: Run focused test to verify RED**

Run:

```bash
python -m pytest python-tests/cover/test_barcode_layout.py -q
```

Expected: FAIL because the shared layout module does not exist.

- [ ] **Step 3: Implement normalized layout**

Use existing `encode_ean13_modules` and `encode_ean_addon_modules`. Return immutable normalized coordinates, keeping all black bars programmatic.

- [ ] **Step 4: Consume layout from Pillow and Qt**

Replace each renderer's independent spacing logic. Draw the first EAN digit to the left of the bars, six-digit groups below each half, and add-on digits above supplement bars using the OCR font role.

- [ ] **Step 5: Run barcode, render and desktop tests**

Run:

```bash
python -m pytest python-tests/cover/test_barcode_layout.py python-tests/cover/test_render.py desktop/tests/test_publisher_workflow.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `fix: match reference EAN barcode typography`

---

### Task 7: Full verification and PR cleanup

**Files:**
- Update: PR #13 description.
- Delete any temporary patch workflow introduced only for implementation.

- [ ] **Step 1: Run shared tests**

```bash
python -m pytest python-tests -q
```

- [ ] **Step 2: Run desktop tests offscreen**

```bash
QT_QPA_PLATFORM=offscreen python -m pytest desktop/tests -q
```

- [ ] **Step 3: Compile sources**

```bash
python -m compileall -q python/src
```

- [ ] **Step 4: Verify GitHub Actions**

Require success for Desktop PySide6 tests on Ubuntu, Windows and macOS, Android debug APK, and Windows portable EXE.

- [ ] **Step 5: Inspect final changed-file list**

Confirm no font files, generated images or temporary workflows remain.

- [ ] **Step 6: Update PR and mark ready**

Document the three root causes, font fallback behavior and fresh test counts. Mark PR #13 ready only after all checks pass.
