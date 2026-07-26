# Output Overflow, Alias Confirmation, and Cover Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every正文 output mode stay inside its physical page, turn medium-confidence title aliases into explicit user decisions, and replace the confusing three-page cover export with a one-page-or-two-page A4 print set plus a separate original-size spread PDF.

**Architecture:** Introduce one shared Word text-metrics module used by both pagination and DOCX writing so line height and paragraph spacing cannot diverge. Keep title-alias decisions in the search pipeline as explicit accepted/ignored inputs, with a small desktop row widget for each pending alias. Replace the current back/spine/front print plan with a single-or-two-page `PrintPlan`, then derive raster PDF, editable DOCX, preview thumbnails, filenames, and atomic export transactions from that same plan.

**Tech Stack:** Python 3.13, python-docx, OOXML, Pillow, pypdf, PySide6, pytest, Kotlin/Android bridge tests, GitHub Actions, PyInstaller.

## Global Constraints

- A5 physical paper size remains exactly 148 × 210 mm.
- 4×6 physical paper size remains exactly 101.6 × 152.4 mm.
- B6-on-A5 uses a 128 × 182 mm finished frame on an A5 physical page.
- A4 four-up and 16-page signature keep their existing imposition order and physical A4 page size.
- Pagination and DOCX writing must use the same fixed line-height and paragraph-spacing values.
- No output path may silently scale a cover to fit A4; all A4 print pages remain 100% scale.
- A split cover print plan has exactly two pages named `back_side` and `front_side`; an independent `spine` page is forbidden.
- The two-page overlap is centered on the spine centerline and is 10 mm total where geometry permits, never below 5 mm.
- Every cover export produces `<書名>-完整書衣-原始尺寸.pdf`, `<書名>-A4拼接列印.pdf`, and `<書名>-A4拼接列印.docx`.
- Medium-confidence aliases do not enter a query plan until the user confirms them.
- Confirmed aliases are not written to permanent cache until the user selects an actual cover candidate.
- Ignoring one alias suppresses it for the current project/search session without deleting other results.
- Missing back-cover imagery must produce a confirmation warning before export.
- Do not add Z-Library, paid APIs, new network providers, or generated cover images.
- Preserve Windows Portable mode and existing credential compatibility.

---

## File Structure

**New shared/core files**

- `python/src/epub_a4_word/text_metrics.py` — fixed Word line-height and paragraph-height calculations shared by pagination and DOCX output.
- `python/src/epub_a4_word/cover/export_plan.py` — immutable export preview/manifest built from one `CoverProject`, including original spread size, A4 `PrintPlan`, and blank-back status.

**New desktop files**

- `python/src/epub_a4_word_desktop/cover/alias_decision_row.py` — one pending/confirmed/ignored alias row with explicit buttons.
- `python/src/epub_a4_word_desktop/cover/export_preview_dialog.py` — preview of original-size output, A4 pages, overlap, filenames, and blank-back confirmation.

**Core files to modify**

- `python/src/epub_a4_word/pagination.py`
- `python/src/epub_a4_word/docx_writer.py`
- `python/src/epub_a4_word/cover/search/models.py`
- `python/src/epub_a4_word/cover/search/query_plan.py`
- `python/src/epub_a4_word/cover/search/pipeline.py`
- `python/src/epub_a4_word/cover/print_plan.py`
- `python/src/epub_a4_word/cover/render.py`
- `python/src/epub_a4_word/cover/pdf_export.py`
- `python/src/epub_a4_word/cover/docx_export.py`
- `python/src/epub_a4_word/cover/service.py`

**Desktop files to modify**

- `python/src/epub_a4_word_desktop/cover/search_controller.py`
- `python/src/epub_a4_word_desktop/cover/search_panel.py`
- `python/src/epub_a4_word_desktop/cover/export_worker.py`
- `python/src/epub_a4_word_desktop/pages/cover_page.py`

**Tests to create or modify**

- Create `python-tests/core/test_text_metrics.py`
- Modify `python-tests/core/test_pagination.py`
- Modify `python-tests/core/test_docx_writer.py`
- Modify `python-tests/test_single_page_blank_page_regression.py`
- Modify `python-tests/cover/test_query_plan.py`
- Modify `python-tests/cover/test_search_pipeline.py`
- Modify `python-tests/cover/test_print_plan.py`
- Modify `python-tests/cover/test_render.py`
- Modify `python-tests/cover/test_pdf_export.py`
- Modify `python-tests/cover/test_docx_export.py`
- Modify `python-tests/cover/test_service.py`
- Create `python-tests/cover/test_export_plan.py`
- Modify `desktop/tests/test_cover_search_free_sources.py`
- Create `desktop/tests/test_alias_decision_row.py`
- Create `desktop/tests/test_export_preview_dialog.py`
- Modify `desktop/tests/test_export_worker.py`
- Modify `desktop/tests/test_cover_page.py`
- Modify `python-tests/test_android_bridge.py`
- Modify `desktop/tests/test_windows_portable_packaging.py`

---

### Task 1: Introduce Shared Fixed Word Text Metrics

**Files:**
- Create: `python/src/epub_a4_word/text_metrics.py`
- Create: `python-tests/core/test_text_metrics.py`

**Interfaces:**
- Produces: `ParagraphMetrics(line_height_pt: float, spacing_after_pt: float)`.
- Produces: `paragraph_metrics(font_pt: float, requested_multiplier: float, spacing_after_pt: float) -> ParagraphMetrics`.
- Produces: `word_safety_points(imposition_mode: str, configured_points: float) -> float`.
- Consumed by Tasks 2 and 3.

- [ ] **Step 1: Write failing fixed-height tests**

```python
from epub_a4_word.text_metrics import paragraph_metrics, word_safety_points


def test_fixed_line_height_is_rounded_up_to_half_point() -> None:
    metrics = paragraph_metrics(8.5, 1.23, 2.5)
    assert metrics.line_height_pt == 11.5
    assert metrics.spacing_after_pt == 2.5


def test_fixed_line_height_never_uses_less_than_130_percent() -> None:
    assert paragraph_metrics(10.0, 1.0, 0.0).line_height_pt == 13.0


def test_all_modes_have_word_bottom_safety() -> None:
    assert word_safety_points("single_a5", 0.0) == 28.0
    assert word_safety_points("single_4x6", 0.0) == 28.0
    assert word_safety_points("four_up", 0.0) == 24.0
    assert word_safety_points("signature16", 0.0) == 24.0
    assert word_safety_points("b6_on_a5", 0.0) == 42.0
```

- [ ] **Step 2: Run tests and verify the module is missing**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/core/test_text_metrics.py -q
```

Expected: collection fails with `ModuleNotFoundError: epub_a4_word.text_metrics`.

- [ ] **Step 3: Implement the independent metrics module**

```python
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ParagraphMetrics:
    line_height_pt: float
    spacing_after_pt: float


def _ceil_half(value: float) -> float:
    return math.ceil(float(value) * 2.0) / 2.0


def paragraph_metrics(
    font_pt: float,
    requested_multiplier: float,
    spacing_after_pt: float,
) -> ParagraphMetrics:
    multiplier = max(float(requested_multiplier), 1.30)
    return ParagraphMetrics(
        line_height_pt=_ceil_half(float(font_pt) * multiplier),
        spacing_after_pt=max(0.0, float(spacing_after_pt)),
    )


_MINIMUM_WORD_SAFETY_PT = {
    "single_a5": 28.0,
    "single_4x6": 28.0,
    "four_up": 24.0,
    "signature16": 24.0,
    "b6_on_a5": 42.0,
}


def word_safety_points(imposition_mode: str, configured_points: float) -> float:
    minimum = _MINIMUM_WORD_SAFETY_PT.get(str(imposition_mode), 24.0)
    return max(float(configured_points), minimum)
```

- [ ] **Step 4: Run focused tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/core/test_text_metrics.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the shared metrics unit**

```bash
git add python/src/epub_a4_word/text_metrics.py python-tests/core/test_text_metrics.py
git commit -m "feat: add shared fixed Word text metrics"
```

---

### Task 2: Make Pagination Use the Shared Metrics in Every Output Mode

**Files:**
- Modify: `python/src/epub_a4_word/pagination.py:14-246`
- Modify: `python-tests/core/test_pagination.py`
- Modify: `python-tests/test_single_page_blank_page_regression.py`

**Interfaces:**
- Consumes: `paragraph_metrics()` and `word_safety_points()` from Task 1.
- Produces: unchanged public `resolve_layout()`, `measure_text()`, and `paginate()` APIs with safer output.
- Produces: `_line_height_for(block: TextBlock, settings: LayoutSettings) -> float` for internal split calculations.

- [ ] **Step 1: Add failing all-mode near-boundary pagination tests**

```python
@pytest.mark.parametrize(
    "mode",
    ["single_a5", "single_4x6", "b6_on_a5", "four_up", "signature16"],
)
def test_mixed_text_never_exceeds_resolved_content_height(mode: str) -> None:
    settings = resolve_layout(LayoutSettings(imposition_mode=mode))
    block = TextBlock(
        (TextRun("魔法禁書目錄 A Certain Magical Index 測試段落。" * 180),),
        style="body",
    )
    pages = paginate((block,), settings, {})
    assert len(pages) >= 2
    assert all(page.used_points <= settings.content_height_pt for page in pages)
```

Add separate assertions that `resolve_layout()` applies safety floors of 28/28/42/24/24 points.

- [ ] **Step 2: Run the tests and verify current estimates are too optimistic**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/core/test_pagination.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: at least one new mixed-text assertion fails or the safety-floor assertions fail.

- [ ] **Step 3: Replace multiplier-only measurements with shared fixed heights**

```python
def _metrics_for(block: TextBlock, settings: LayoutSettings):
    font_pt = _font_for(block, settings)
    spacing = (
        settings.heading_spacing_pt
        if block.style == "heading"
        else settings.paragraph_spacing_pt
    )
    return paragraph_metrics(font_pt, settings.line_spacing, spacing)
```

Set `pagination_safety = word_safety_points(settings.imposition_mode, settings.pagination_safety_pt)`. Use `metrics.line_height_pt` in `measure_text()` and `_find_split_index()`.

- [ ] **Step 4: Run pagination and blank-page tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/core/test_text_metrics.py \
  python-tests/core/test_pagination.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit pagination changes**

```bash
git add python/src/epub_a4_word/pagination.py \
  python-tests/core/test_pagination.py \
  python-tests/test_single_page_blank_page_regression.py
git commit -m "fix: keep pagination inside every page mode"
```

---

### Task 3: Make DOCX Paragraph Height Match Pagination Exactly

**Files:**
- Modify: `python/src/epub_a4_word/docx_writer.py:13-247`
- Modify: `python-tests/core/test_docx_writer.py`
- Modify: `python-tests/test_single_page_blank_page_regression.py`

**Interfaces:**
- Consumes: `paragraph_metrics()` from Task 1.
- Produces: DOCX paragraph OOXML with `w:lineRule="exact"` and the same line height used by pagination.
- Keeps: public `write_docx()` signature unchanged.

- [ ] **Step 1: Add failing OOXML line-rule tests**

```python
spacing = paragraph.find("w:pPr/w:spacing", namespaces=NS)
assert spacing.get(f"{{{NS['w']}}}lineRule") == "exact"
assert int(spacing.get(f"{{{NS['w']}}}line")) == 230
```

Add a mixed-text fixture near the page limit and assert the generated DOCX contains the same number of content rows/pages as `paginate()`.

- [ ] **Step 2: Run tests and verify Word still receives multiple line spacing**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/core/test_docx_writer.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: new `lineRule="exact"` assertions fail.

- [ ] **Step 3: Set exact line spacing for body, heading, and fallback text**

```python
metrics = paragraph_metrics(
    font_size,
    settings.line_spacing,
    settings.heading_spacing_pt
    if block.style == "heading"
    else settings.paragraph_spacing_pt,
)
fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
fmt.line_spacing = Pt(metrics.line_height_pt)
fmt.space_after = Pt(metrics.spacing_after_pt)
```

Keep page-number paragraphs at 8 pt and image paragraph spacing aligned with `measure_image()`.

- [ ] **Step 4: Run focused writer tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/core/test_text_metrics.py \
  python-tests/core/test_pagination.py \
  python-tests/core/test_docx_writer.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit DOCX metric synchronization**

```bash
git add python/src/epub_a4_word/docx_writer.py \
  python-tests/core/test_docx_writer.py \
  python-tests/test_single_page_blank_page_regression.py
git commit -m "fix: match DOCX line height to pagination"
```

---

### Task 4: Add Explicit Accepted and Ignored Alias Inputs to the Search Pipeline

**Files:**
- Modify: `python/src/epub_a4_word/cover/search/models.py:37-60,228-263`
- Modify: `python/src/epub_a4_word/cover/search/query_plan.py:160-235`
- Modify: `python/src/epub_a4_word/cover/search/pipeline.py:65-201`
- Modify: `python-tests/cover/test_query_plan.py`
- Modify: `python-tests/cover/test_search_pipeline.py`

**Interfaces:**
- Produces: `alias_key(alias: ResolvedAlias) -> str`.
- Changes: `BookCoverSearchPipeline.search(..., accepted_aliases: tuple[ResolvedAlias, ...] = (), ignored_alias_keys: frozenset[str] = frozenset()) -> SearchResponse`.
- Changes: `SearchResponse` gains `pending_aliases: tuple[ResolvedAlias, ...]` while retaining `resolved_aliases`.

- [ ] **Step 1: Write failing decision-state tests**

```python
def test_medium_alias_does_not_enter_plan_until_accepted(identity) -> None:
    alias = ResolvedAlias("A Certain Magical Index", "en", "wikidata", "medium")
    initial = build_query_plan(identity, aliases=(alias,))
    accepted = build_query_plan(identity, aliases=(alias,), accepted_aliases=(alias,))
    assert "A Certain Magical Index" not in [item.value for item in initial.items]
    assert "A Certain Magical Index" in [item.value for item in accepted.items]
```

Add an ignored-alias test that checks it does not return in `pending_aliases`.

- [ ] **Step 2: Run tests and verify signatures are missing**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_query_plan.py \
  python-tests/cover/test_search_pipeline.py -q
```

Expected: failures for unknown accepted/ignored arguments or missing `pending_aliases`.

- [ ] **Step 3: Implement stable keys and accepted-alias promotion**

```python
def alias_key(alias: ResolvedAlias) -> str:
    return "|".join((
        alias.source.casefold().strip(),
        (alias.language or "").casefold().strip(),
        " ".join(alias.value.casefold().split()),
    ))
```

Confirmed aliases enter the plan as high-confidence title queries with reason `user-confirmed alias`. Ignored keys are filtered before pending aliases and query construction.

- [ ] **Step 4: Run focused pipeline tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_query_plan.py \
  python-tests/cover/test_search_pipeline.py \
  python-tests/cover/test_wikidata.py -q
```

Expected: all pass and provider error isolation remains intact.

- [ ] **Step 5: Commit pipeline decision support**

```bash
git add python/src/epub_a4_word/cover/search/models.py \
  python/src/epub_a4_word/cover/search/query_plan.py \
  python/src/epub_a4_word/cover/search/pipeline.py \
  python-tests/cover/test_query_plan.py \
  python-tests/cover/test_search_pipeline.py
git commit -m "feat: add explicit alias confirmation state"
```

---

### Task 5: Add Desktop Alias Confirmation and Ignore Controls

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/alias_decision_row.py`
- Modify: `python/src/epub_a4_word_desktop/cover/search_controller.py:41-227`
- Modify: `python/src/epub_a4_word_desktop/cover/search_panel.py:149-420`
- Create: `desktop/tests/test_alias_decision_row.py`
- Modify: `desktop/tests/test_cover_search_free_sources.py`

**Interfaces:**
- Produces: `AliasDecisionRow(alias: ResolvedAlias)` with signals `accepted(object)` and `ignored(str)`.
- Changes: `SharedSearchFacade.search_public(..., accepted_aliases=(), ignored_alias_keys=frozenset())`.
- Changes: `SearchController.search_public(..., accepted_aliases=(), ignored_alias_keys=frozenset())`.
- Produces: `SearchController.remember_confirmed_aliases(metadata, aliases, isbn="")`.

- [ ] **Step 1: Write failing row-widget tests**

```python
def test_alias_row_emits_accept_and_ignore(qtbot) -> None:
    alias = ResolvedAlias("A Certain Magical Index", "en", "wikidata", "medium")
    row = AliasDecisionRow(alias)
    qtbot.addWidget(row)
    with qtbot.waitSignal(row.accepted) as accepted:
        qtbot.mouseClick(row.accept_button, Qt.MouseButton.LeftButton)
    assert accepted.args == [alias]
```

Add panel tests verifying acceptance triggers a new search and ignore removes only that alias.

- [ ] **Step 2: Run desktop tests and verify the widget is absent**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest desktop/tests/test_alias_decision_row.py \
  desktop/tests/test_cover_search_free_sources.py -q
```

Expected: import or attribute failures.

- [ ] **Step 3: Implement row widget and panel state**

`CoverSearchPanel` owns `accepted_aliases: dict[str, ResolvedAlias]` and `ignored_alias_keys: set[str]`. Confirming adds the alias and reruns search; ignoring removes it from the visible pending list. Selecting a cover calls `remember_confirmed_aliases()` so accepted aliases persist only after a real candidate is selected.

- [ ] **Step 4: Run desktop alias tests**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest desktop/tests/test_alias_decision_row.py \
  desktop/tests/test_cover_search_free_sources.py \
  desktop/tests/test_round2_desktop.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit desktop alias decisions**

```bash
git add python/src/epub_a4_word_desktop/cover/alias_decision_row.py \
  python/src/epub_a4_word_desktop/cover/search_controller.py \
  python/src/epub_a4_word_desktop/cover/search_panel.py \
  desktop/tests/test_alias_decision_row.py \
  desktop/tests/test_cover_search_free_sources.py
git commit -m "feat: add alias confirm and ignore controls"
```

---

### Task 6: Replace Three-Page Cover Splitting with One-or-Two-Page A4 Planning

**Files:**
- Modify: `python/src/epub_a4_word/cover/print_plan.py:16-265`
- Modify: `python-tests/cover/test_print_plan.py`

**Interfaces:**
- Changes: `PrintPlan.mode` becomes `Literal["single", "two_page"]`.
- Changes: split page names become `back_side` and `front_side`.
- Changes: `PrintMark` gains `role` and `line_style`.
- Keeps: `build_print_plan(layout: CoverLayout) -> PrintPlan`.

- [ ] **Step 1: Replace old three-page expectations with failing two-page tests**

```python
def test_a5_spread_splits_into_two_pages_around_spine_center(sample_project) -> None:
    layout = calculate_layout(sample_project(trim=(148.0, 210.0)))
    plan = build_print_plan(layout)
    assert plan.mode == "two_page"
    assert [page.name for page in plan.pages] == ["back_side", "front_side"]
    assert not any(page.name == "spine" for page in plan.pages)
```

Also assert union coverage, 100% scale, overlap width, and marks outside destination rectangles.

- [ ] **Step 2: Run tests and verify current plan still returns three pages**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_print_plan.py -q
```

Expected: old `back/spine/front` result fails.

- [ ] **Step 3: Implement the centerline split**

```python
spine_center = layout.spine_rect.x_mm + layout.spine_rect.width_mm / 2.0
back_right = spine_center + 5.0
front_left = spine_center - 5.0
```

Reduce total overlap in 0.5 mm steps only when needed, never below 5 mm total. Raise `CoverLayoutError` instead of scaling if either tile still cannot fit A4.

- [ ] **Step 4: Run print-plan tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_print_plan.py -q
```

Expected: all pass and no page named `spine` exists.

- [ ] **Step 5: Commit the two-page plan**

```bash
git add python/src/epub_a4_word/cover/print_plan.py \
  python-tests/cover/test_print_plan.py
git commit -m "fix: split large cover exports into two A4 pages"
```

---

### Task 7: Render the Same Readable Marks in A4 PDF and DOCX

**Files:**
- Modify: `python/src/epub_a4_word/cover/render.py:512-558`
- Modify: `python/src/epub_a4_word/cover/docx_export.py:28-314`
- Modify: `python-tests/cover/test_render.py`
- Modify: `python-tests/cover/test_docx_export.py`

**Interfaces:**
- Consumes: styled `PrintMark` and two-page plan from Task 6.
- Produces: identical semantic labels in raster PDF pages and editable DOCX sections.

- [ ] **Step 1: Write failing readable-mark tests**

Assert these strings exist in plan/DOCX output:

```text
第 1 頁／2：封底側
第 2 頁／2：正面側
100% 實際大小列印，請關閉「符合紙張大小」
重疊黏貼區
```

Assert DOCX section count is two and no `書脊` page label exists.

- [ ] **Step 2: Run tests and verify old tiny labels remain**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_render.py \
  python-tests/cover/test_docx_export.py -q
```

Expected: section count and label assertions fail.

- [ ] **Step 3: Implement semantic mark rendering**

Pillow uses larger label/instruction fonts and physical dashed/dotted segments. DOCX maps mark roles to 10 pt page labels, 8 pt instructions, solid crop lines, and dashed overlap/alignment lines. Remove the hard-coded 5 mm direction text and render all marks from `PrintPlan`.

- [ ] **Step 4: Run render and DOCX tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_print_plan.py \
  python-tests/cover/test_render.py \
  python-tests/cover/test_docx_export.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit shared mark rendering**

```bash
git add python/src/epub_a4_word/cover/render.py \
  python/src/epub_a4_word/cover/docx_export.py \
  python-tests/cover/test_render.py \
  python-tests/cover/test_docx_export.py
git commit -m "feat: add readable A4 cover assembly marks"
```

---

### Task 8: Add Original-Size Spread PDF and an Export Manifest

**Files:**
- Create: `python/src/epub_a4_word/cover/export_plan.py`
- Modify: `python/src/epub_a4_word/cover/pdf_export.py:16-146`
- Modify: `python/src/epub_a4_word/cover/service.py:450-463`
- Create: `python-tests/cover/test_export_plan.py`
- Modify: `python-tests/cover/test_pdf_export.py`
- Modify: `python-tests/cover/test_service.py`

**Interfaces:**
- Produces: `CoverExportPlan(original_size_mm, print_plan, back_cover_blank)`.
- Produces: `build_export_plan(project) -> CoverExportPlan`.
- Produces: `export_original_pdf(project, output_path, dpi=300) -> ExportResult`.
- Produces: `service.export_cover_bundle(project_json, original_pdf_path, print_pdf_path, print_docx_path, dpi=300)`.
- Keeps: `service.export_cover()` as compatibility wrapper.

- [ ] **Step 1: Write failing original-size and blank-back tests**

```python
def test_original_pdf_uses_exact_spread_size(sample_project, tmp_path) -> None:
    project = sample_project(trim=(148.0, 210.0))
    result = export_original_pdf(project, tmp_path / "original.pdf", dpi=300)
    reader = PdfReader(result.path)
    assert len(reader.pages) == 1
```

Assert MediaBox equals `layout.bleed_rect` within 0.05 mm and blank back is detected when no visible image intersects `layout.back_rect`.

- [ ] **Step 2: Run tests and verify functions are missing**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_export_plan.py \
  python-tests/cover/test_pdf_export.py \
  python-tests/cover/test_service.py -q
```

Expected: import/signature failures.

- [ ] **Step 3: Implement export-plan inspection and original PDF**

`build_export_plan()` calculates layout and A4 plan once, and detects a visible back image by transformed-rectangle intersection plus nonzero opacity. `export_original_pdf()` renders one spread page and writes exact custom MediaBox/CropBox/TrimBox values. `export_cover_bundle()` returns separate `original_pdf`, `print_pdf`, `print_docx`, and print-plan metadata.

- [ ] **Step 4: Run export-plan and service tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_export_plan.py \
  python-tests/cover/test_pdf_export.py \
  python-tests/cover/test_docx_export.py \
  python-tests/cover/test_service.py -q
```

Expected: all pass and compatibility tests remain green.

- [ ] **Step 5: Commit original-size export support**

```bash
git add python/src/epub_a4_word/cover/export_plan.py \
  python/src/epub_a4_word/cover/pdf_export.py \
  python/src/epub_a4_word/cover/service.py \
  python-tests/cover/test_export_plan.py \
  python-tests/cover/test_pdf_export.py \
  python-tests/cover/test_service.py
git commit -m "feat: export original-size cover spread PDF"
```

---

### Task 9: Add Export Preview, Blank-Back Confirmation, and Three-File Atomic Output

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/export_preview_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/cover/export_worker.py:20-178`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py:78-116,443-467`
- Create: `desktop/tests/test_export_preview_dialog.py`
- Modify: `desktop/tests/test_export_worker.py`
- Modify: `desktop/tests/test_cover_page.py`

**Interfaces:**
- Produces: `ExportPaths(original_pdf: Path, print_pdf: Path, print_docx: Path)`.
- Changes: `export_paths(project_json, output_dir) -> ExportPaths`.
- Produces: `ExportPreviewDialog(project_json, paths, dpi)`.
- Changes: `ExportWorker(project_json, paths: ExportPaths, dpi: int)`.

- [ ] **Step 1: Write failing filename, preview, and rollback tests**

```python
def test_export_paths_have_clear_three_file_names(tmp_path) -> None:
    paths = export_paths(_project_json(tmp_path), tmp_path / "exports")
    assert paths.original_pdf.name == "範例書-完整書衣-原始尺寸.pdf"
    assert paths.print_pdf.name == "範例書-A4拼接列印.pdf"
    assert paths.print_docx.name == "範例書-A4拼接列印.docx"
```

Add dialog tests for page count, thumbnails, overlap, filenames, and explicit blank-back continuation. Add rollback test for failure on the third replacement.

- [ ] **Step 2: Run desktop tests and verify two-file assumptions fail**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest desktop/tests/test_export_preview_dialog.py \
  desktop/tests/test_export_worker.py \
  desktop/tests/test_cover_page.py -q
```

Expected: missing dialog/dataclass and old two-path assertions fail.

- [ ] **Step 3: Implement preview and atomic three-file transaction**

The dialog displays original size, A4 page count, 72-DPI thumbnails from `render_print_page()`, overlap width, and filenames. Blank-back projects require `返回補上封底` or `仍然輸出空白封底`. Transaction progress is `準備`, `輸出完整尺寸 PDF`, `輸出 A4 PDF`, `輸出 A4 DOCX`, `完成`. All three targets use backups and rollback together.

- [ ] **Step 4: Connect the dialog before starting the worker**

```python
paths = export_paths(self.controller.project_json, output_dir)
dialog = ExportPreviewDialog(self.controller.project_json, paths, dpi, self)
if dialog.exec() != QDialog.DialogCode.Accepted:
    self.status_label.setText("已取消封面輸出。")
    return
worker = ExportWorker(self.controller.project_json, paths, dpi)
```

Completion UI lists all three files separately.

- [ ] **Step 5: Run desktop export tests**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest desktop/tests/test_export_preview_dialog.py \
  desktop/tests/test_export_worker.py \
  desktop/tests/test_cover_page.py \
  desktop/tests/test_round2_desktop.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit desktop export flow**

```bash
git add python/src/epub_a4_word_desktop/cover/export_preview_dialog.py \
  python/src/epub_a4_word_desktop/cover/export_worker.py \
  python/src/epub_a4_word_desktop/pages/cover_page.py \
  desktop/tests/test_export_preview_dialog.py \
  desktop/tests/test_export_worker.py \
  desktop/tests/test_cover_page.py
git commit -m "feat: preview and export clear cover print files"
```

---

### Task 10: Update Android Bridge Regression Coverage and User Documentation

**Files:**
- Modify: `python-tests/test_android_bridge.py`
- Modify: `README.md`
- Modify: `BUILDING.md`
- Modify: `BUILD_STATUS.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add Android bridge pagination-safety regression**

Convert a long mixed CJK/Latin EPUB through the bridge using `single_a5`; assert conversion succeeds, produces more than one logical page, and returns no error payload.

- [ ] **Step 2: Run Android bridge tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/test_android_bridge.py -q
```

Expected: all pass.

- [ ] **Step 3: Update user-facing documentation**

Document fixed Word line heights, alias confirmation, three cover files, one-or-two-page A4 output, 100% print settings, blank-back warning, and the need to regenerate old outputs.

- [ ] **Step 4: Commit tests and documentation**

```bash
git add python-tests/test_android_bridge.py \
  README.md BUILDING.md BUILD_STATUS.md CHANGELOG.md
git commit -m "docs: explain safe body and cover export workflows"
```

---

### Task 11: Run Full Cross-Platform Verification and Build a Windows Portable Artifact

**Files:**
- Modify only if failing checks require it: `.github/workflows/desktop.yml`
- Modify only if failing checks require it: `.github/workflows/android.yml`
- Modify only if failing checks require it: `.github/workflows/windows-portable.yml`
- Modify: `desktop/tests/test_windows_portable_packaging.py` when new modules need explicit package assertions.

- [ ] **Step 1: Run complete shared Python tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python python -m pytest python-tests -q
```

Expected: zero failures.

- [ ] **Step 2: Run complete desktop tests**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest desktop/tests -q
```

Expected: zero failures. If local PySide6 is unavailable, this exact suite must pass in GitHub Actions on Windows, macOS, and Ubuntu.

- [ ] **Step 3: Run compile and project verification**

```bash
python -m compileall -q python/src app/src/main/python scripts packaging
PYTHONPATH=.:python/src:app/src/main/python python scripts/verify_project.py
```

Expected: both exit 0.

- [ ] **Step 4: Inspect final diff and packaging**

```bash
git diff --check
git status --short
```

Assert packaging includes `text_metrics.py`, `export_plan.py`, `alias_decision_row.py`, and `export_preview_dialog.py`.

- [ ] **Step 5: Push implementation branch and open draft PR**

```bash
git push -u origin agent/impl-output-overflow-alias-cover-export
```

Required exact-HEAD workflows: Desktop Windows/macOS/Ubuntu success, Android debug APK success, Windows Portable focused tests/build/directory verification/packaged EXE smoke/artifact upload success.

- [ ] **Step 6: Download and inspect Portable artifact**

Verify `EPUB2A4.exe`, `_internal/PySide6/plugins/platforms/qwindows.dll`, and `portable.flag`; compare the inner ZIP SHA-256 to the uploaded report.

- [ ] **Step 7: Request code review and merge only after rerun**

Fix every critical or important review finding, rerun exact-HEAD CI, and report the remaining real-device Microsoft Word/printing caveat.

---

## Self-Review Checklist

- Every approved specification requirement maps to Tasks 1-11.
- Pagination and DOCX writing use one shared metrics module and identical numeric line heights.
- Medium aliases are never promoted without explicit acceptance.
- Permanent alias cache writes remain delayed until a cover is selected.
- Split print plans contain no independent `spine` page.
- PDF, DOCX, and preview all consume the same `PrintPlan`.
- Original-size PDF is separate from the A4 print PDF.
- Three-file replacement is atomic.
- No automatic scaling, paid services, Z-Library, or image generation is introduced.
- No unresolved placeholders or contradictory signatures remain.
