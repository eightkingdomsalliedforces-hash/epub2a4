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

Run:

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

Add a parametrized test that constructs repeated mixed CJK/Latin paragraphs and verifies pagination occurs before `used_points` exceeds `content_height_pt`:

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

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/core/test_pagination.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: at least one new mixed-text assertion fails or the safety-floor assertions fail.

- [ ] **Step 3: Replace multiplier-only measurements with shared fixed heights**

Update `resolve_layout()` so `pagination_safety` is always:

```python
pagination_safety = word_safety_points(
    settings.imposition_mode,
    settings.pagination_safety_pt,
)
```

Update text measurement and split calculations:

```python
def _metrics_for(block: TextBlock, settings: LayoutSettings):
    font_pt = _font_for(block, settings)
    spacing = (
        settings.heading_spacing_pt
        if block.style == "heading"
        else settings.paragraph_spacing_pt
    )
    return paragraph_metrics(font_pt, settings.line_spacing, spacing)


def measure_text(block: TextBlock, settings: LayoutSettings) -> float:
    settings = resolve_layout(settings)
    metrics = _metrics_for(block, settings)
    lines = _estimated_line_count(block, settings)
    return lines * metrics.line_height_pt + metrics.spacing_after_pt
```

Use the same `metrics.line_height_pt` inside `_find_split_index()` rather than `font_pt * settings.line_spacing`.

- [ ] **Step 4: Run pagination and blank-page tests**

Run:

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
git add \
  python/src/epub_a4_word/pagination.py \
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

Generate one body paragraph and one heading, open `word/document.xml`, and assert:

```python
spacing = paragraph.find("w:pPr/w:spacing", namespaces=NS)
assert spacing.get(f"{{{NS['w']}}}lineRule") == "exact"
assert int(spacing.get(f"{{{NS['w']}}}line")) == 230  # 11.5 pt in twentieths
```

Add a mixed-text fixture near the page limit and assert the generated DOCX contains the same number of content rows/pages as `paginate()`.

- [ ] **Step 2: Run tests and verify Word still receives multiple line spacing**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/core/test_docx_writer.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: new `lineRule="exact"` assertions fail.

- [ ] **Step 3: Set exact line spacing for body, heading, and fallback text**

Import `WD_LINE_SPACING` and set paragraph formatting in `_add_text_block()`:

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

Keep page-number paragraphs at their existing explicit 8 pt height and keep image paragraph spacing in the same height budget already used by `measure_image()`.

- [ ] **Step 4: Run focused writer tests and optional LibreOffice page-count checks**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/core/test_text_metrics.py \
  python-tests/core/test_pagination.py \
  python-tests/core/test_docx_writer.py \
  python-tests/test_single_page_blank_page_regression.py -q
```

Expected: all tests pass; environments with LibreOffice report no extra PDF page.

- [ ] **Step 5: Commit DOCX metric synchronization**

```bash
git add \
  python/src/epub_a4_word/docx_writer.py \
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
- Changes: `SearchResponse` gains `pending_aliases: tuple[ResolvedAlias, ...]` while retaining `resolved_aliases` for compatibility.
- Consumed by Tasks 5 and 6.

- [ ] **Step 1: Write failing decision-state tests**

```python
def test_medium_alias_does_not_enter_plan_until_accepted(identity) -> None:
    alias = ResolvedAlias("A Certain Magical Index", "en", "wikidata", "medium")
    initial = build_query_plan(identity, aliases=(alias,))
    accepted = build_query_plan(
        identity,
        aliases=(alias,),
        accepted_aliases=(alias,),
    )
    assert "A Certain Magical Index" not in [item.value for item in initial.items]
    assert "A Certain Magical Index" in [item.value for item in accepted.items]


def test_ignored_alias_is_not_returned_as_pending(pipeline, metadata) -> None:
    response = pipeline.search(
        metadata,
        selection=ProviderSelection(open_library=True, google_books=False, gutendex=False),
        ignored_alias_keys=frozenset({"wikidata|en|a certain magical index"}),
    )
    assert all(alias.value != "A Certain Magical Index" for alias in response.pending_aliases)
```

- [ ] **Step 2: Run tests and verify signatures are missing**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/cover/test_query_plan.py \
  python-tests/cover/test_search_pipeline.py -q
```

Expected: failures for unknown `accepted_aliases`, `ignored_alias_keys`, or `pending_aliases`.

- [ ] **Step 3: Implement stable alias keys and accepted-alias promotion**

Use a stable key:

```python
def alias_key(alias: ResolvedAlias) -> str:
    return "|".join(
        (
            alias.source.casefold().strip(),
            (alias.language or "").casefold().strip(),
            " ".join(alias.value.casefold().split()),
        )
    )
```

`build_query_plan()` must append a confirmed alias as a high-confidence title item without mutating the original resolver result:

```python
for alias in accepted_aliases:
    append(
        kind="title",
        value=alias.value,
        language=alias.language or "",
        confidence="high",
        source=alias.source,
        reason="user-confirmed alias",
    )
```

In `BookCoverSearchPipeline.search()`, filter ignored keys, merge accepted aliases before the final plan, and return remaining medium aliases as `pending_aliases`.

- [ ] **Step 4: Run focused pipeline tests**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/cover/test_query_plan.py \
  python-tests/cover/test_search_pipeline.py \
  python-tests/cover/test_wikidata.py -q
```

Expected: all tests pass and provider error isolation remains intact.

- [ ] **Step 5: Commit pipeline decision support**

```bash
git add \
  python/src/epub_a4_word/cover/search/models.py \
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
    with qtbot.waitSignal(row.ignored) as ignored:
        qtbot.mouseClick(row.ignore_button, Qt.MouseButton.LeftButton)
    assert ignored.args == [alias_key(alias)]
```

Add panel tests verifying pending aliases appear as separate rows, acceptance triggers a new search, and ignore removes only that row.

- [ ] **Step 2: Run desktop tests and verify the widget is absent**

Run:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  desktop/tests/test_alias_decision_row.py \
  desktop/tests/test_cover_search_free_sources.py -q
```

Expected: import or attribute failures.

- [ ] **Step 3: Implement the row widget and panel state**

`AliasDecisionRow` displays alias value, language, source, joined reasons, and two buttons. `CoverSearchPanel` owns:

```python
self.accepted_aliases: dict[str, ResolvedAlias] = {}
self.ignored_alias_keys: set[str] = set()
```

On accept:

```python
key = alias_key(alias)
self.accepted_aliases[key] = alias
self.ignored_alias_keys.discard(key)
self._search()
```

On ignore:

```python
key = alias_key(alias)
self.accepted_aliases.pop(key, None)
self.ignored_alias_keys.add(key)
self._rebuild_alias_rows(())
```

Pass both collections through the controller. When a cover candidate is selected, call `remember_confirmed_aliases()` so accepted aliases are persisted only at that point.

- [ ] **Step 4: Run desktop alias tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  desktop/tests/test_alias_decision_row.py \
  desktop/tests/test_cover_search_free_sources.py \
  desktop/tests/test_round2_desktop.py -q
```

Expected: all tests pass; existing candidate cards and provider switches still work.

- [ ] **Step 5: Commit desktop alias decisions**

```bash
git add \
  python/src/epub_a4_word_desktop/cover/alias_decision_row.py \
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
- Changes: `PrintMark` gains `role: Literal["crop", "alignment", "overlap", "label", "instruction"]` and `line_style: Literal["solid", "dashed", "dotted"] = "solid"`.
- Keeps: `build_print_plan(layout: CoverLayout) -> PrintPlan`.
- Consumed by Tasks 7, 8, and 9.

- [ ] **Step 1: Replace old three-page expectations with failing two-page tests**

```python
def test_a5_spread_splits_into_two_pages_around_spine_center(sample_project) -> None:
    layout = calculate_layout(sample_project(trim=(148.0, 210.0)))
    plan = build_print_plan(layout)
    assert plan.mode == "two_page"
    assert [page.name for page in plan.pages] == ["back_side", "front_side"]
    assert all(page.scale == 1.0 for page in plan.pages)
    assert not any(page.name == "spine" for page in plan.pages)
    overlap = min(plan.pages[0].right_overlap_mm, plan.pages[1].left_overlap_mm)
    assert overlap * 2 == pytest.approx(10.0)
```

Also assert the union of both source rectangles covers `layout.bleed_rect`, each tile fits its chosen A4 orientation, and mark labels lie outside `destination_rect`.

- [ ] **Step 2: Run tests and verify the current plan still returns three pages**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_print_plan.py -q
```

Expected: tests report `['back', 'spine', 'front']` instead of two pages.

- [ ] **Step 3: Implement the centerline split**

Use:

```python
spine_center = layout.spine_rect.x_mm + layout.spine_rect.width_mm / 2.0
overlap_each_side = 5.0
back_right = spine_center + overlap_each_side
front_left = spine_center - overlap_each_side
```

Build:

```python
back_source = RectMm(
    layout.bleed_rect.x_mm,
    layout.bleed_rect.y_mm,
    back_right - layout.bleed_rect.x_mm,
    layout.bleed_rect.height_mm,
)
front_source = RectMm(
    front_left,
    layout.bleed_rect.y_mm,
    layout.bleed_rect.right_mm - front_left,
    layout.bleed_rect.height_mm,
)
```

If either tile cannot fit A4 at 1:1, reduce total overlap down to 5 mm in 0.5 mm steps. If no 5 mm-overlap plan fits, raise `CoverLayoutError` with both tile dimensions and the statement that automatic scaling is disabled.

Generate readable labels and instructions as `PrintMark` records from the same plan.

- [ ] **Step 4: Run print-plan tests**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/cover/test_print_plan.py -q
```

Expected: all tests pass and no page named `spine` exists.

- [ ] **Step 5: Commit the two-page plan**

```bash
git add \
  python/src/epub_a4_word/cover/print_plan.py \
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
- Consumes: styled `PrintMark` and two-page `PrintPlan` from Task 6.
- Produces: identical semantic labels in raster PDF pages and editable DOCX sections.
- Keeps: `render_print_page()` and `export_docx()` public signatures.

- [ ] **Step 1: Write failing readable-mark tests**

For rendered pages, assert a label/instruction mark exists with these exact strings:

```text
第 1 頁／2：封底側
第 2 頁／2：正面側
100% 實際大小列印，請關閉「符合紙張大小」
重疊黏貼區
```

For DOCX XML, assert both page labels and instructions occur, section count is two, and there is no `書脊` page label.

- [ ] **Step 2: Run tests and verify old tiny labels remain**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/cover/test_render.py \
  python-tests/cover/test_docx_export.py -q
```

Expected: section count and label assertions fail.

- [ ] **Step 3: Implement semantic mark rendering**

In Pillow rendering:

- `label` uses at least `round(dpi / 9)` pixels, not `dpi / 12`.
- `instruction` uses at least `round(dpi / 12)` pixels.
- `dashed` and `dotted` line styles are drawn by segmenting the line in physical millimetres.
- Mark rectangles remain outside `page.destination_rect`.

In DOCX rendering:

- Map `back_side` and `front_side` to the same exact strings.
- Use 10 pt for page labels and 8 pt for instructions.
- Use VML dash styles for overlap/alignment lines and solid lines for crop marks.
- Remove the hard-coded `← 5 mm 拼接重疊區 →` shape; build all text from `page.marks`.

- [ ] **Step 4: Run render and DOCX export tests**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/cover/test_print_plan.py \
  python-tests/cover/test_render.py \
  python-tests/cover/test_docx_export.py -q
```

Expected: all tests pass and A4 PDF/DOCX use the same page names and marks.

- [ ] **Step 5: Commit shared mark rendering**

```bash
git add \
  python/src/epub_a4_word/cover/render.py \
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
- Produces: `build_export_plan(project: CoverProject) -> CoverExportPlan`.
- Produces: `export_original_pdf(project, output_path, dpi=300) -> ExportResult`.
- Produces: `service.export_cover_bundle(project_json, original_pdf_path, print_pdf_path, print_docx_path, dpi=300) -> dict[str, object]`.
- Keeps: `service.export_cover()` as a compatibility wrapper for the previous A4 PDF + DOCX pair.

- [ ] **Step 1: Write failing original-size and blank-back tests**

```python
def test_original_pdf_uses_exact_spread_size(sample_project, tmp_path) -> None:
    project = sample_project(trim=(148.0, 210.0))
    result = export_original_pdf(project, tmp_path / "original.pdf", dpi=300)
    reader = PdfReader(result.path)
    assert len(reader.pages) == 1
    layout = calculate_layout(project)
    assert points_to_mm(float(reader.pages[0].mediabox.width)) == pytest.approx(
        layout.bleed_rect.width_mm, abs=0.05
    )


def test_export_plan_reports_blank_back(sample_project) -> None:
    plan = build_export_plan(sample_project(trim=(148.0, 210.0)))
    assert plan.back_cover_blank is True
```

- [ ] **Step 2: Run tests and verify functions are missing**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/cover/test_export_plan.py \
  python-tests/cover/test_pdf_export.py \
  python-tests/cover/test_service.py -q
```

Expected: import/signature failures.

- [ ] **Step 3: Implement export-plan inspection and original PDF**

`build_export_plan()` calculates layout once, builds the A4 plan once, and sets `back_cover_blank` by checking visible image elements whose transformed rectangle intersects `layout.back_rect` and whose effective opacity is greater than zero.

`export_original_pdf()` renders `render_spread(project, dpi)`, writes one raster PDF page, normalizes MediaBox/CropBox/TrimBox to `layout.bleed_rect.width_mm × layout.bleed_rect.height_mm`, and validates the physical size within 0.05 mm.

`export_cover_bundle()` returns:

```python
{
    "original_pdf": _result_dict(original_result),
    "print_pdf": _result_dict(print_pdf_result),
    "print_docx": _result_dict(print_docx_result),
    "print_plan": {
        "mode": export_plan.print_plan.mode,
        "page_count": len(export_plan.print_plan.pages),
        "overlap_mm": export_plan.overlap_mm,
        "back_cover_blank": export_plan.back_cover_blank,
    },
    "dpi": dpi,
}
```

- [ ] **Step 4: Run export-plan and service tests**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  python-tests/cover/test_export_plan.py \
  python-tests/cover/test_pdf_export.py \
  python-tests/cover/test_docx_export.py \
  python-tests/cover/test_service.py -q
```

Expected: all tests pass; old compatibility service tests continue to pass.

- [ ] **Step 5: Commit original-size export support**

```bash
git add \
  python/src/epub_a4_word/cover/export_plan.py \
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
- Produces: `ExportPreviewDialog(project_json, paths, dpi)` with `confirmed_export` state.
- Changes: `ExportWorker(project_json, paths: ExportPaths, dpi: int)`.

- [ ] **Step 1: Write failing filename, preview, and rollback tests**

```python
def test_export_paths_have_clear_three_file_names(tmp_path) -> None:
    paths = export_paths(_project_json(tmp_path), tmp_path / "exports")
    assert paths.original_pdf.name == "範例書-完整書衣-原始尺寸.pdf"
    assert paths.print_pdf.name == "範例書-A4拼接列印.pdf"
    assert paths.print_docx.name == "範例書-A4拼接列印.docx"
```

Add dialog tests that show one/two A4 pages from `build_export_plan()`, list all three filenames, show overlap width, and require explicit continuation when `back_cover_blank` is true.

Add a transaction test where the third replacement fails and all three previous files are restored.

- [ ] **Step 2: Run desktop tests and verify two-file assumptions fail**

Run:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  desktop/tests/test_export_preview_dialog.py \
  desktop/tests/test_export_worker.py \
  desktop/tests/test_cover_page.py -q
```

Expected: missing dialog/dataclass and old two-path assertions fail.

- [ ] **Step 3: Implement preview and atomic three-file transaction**

`ExportPreviewDialog` must:

- show original-size width × height in mm;
- show whether A4 output is one or two pages;
- render each `PrintPage` at 72 DPI using `render_print_page()` and display scaled thumbnails;
- show page names, overlap width, and all filenames;
- present `返回補上封底` and `仍然輸出空白封底` when blank-back status is true;
- enable the final export button only after the user explicitly chooses to continue in the blank-back case.

`_export_transaction()` creates three temporary outputs, validates both PDFs and the DOCX, then replaces all three targets atomically with backups for each existing file.

Progress stages become:

```python
["準備", "輸出完整尺寸 PDF", "輸出 A4 PDF", "輸出 A4 DOCX", "完成"]
```

- [ ] **Step 4: Connect the dialog before starting the worker**

In `CoverPage._start_export()`:

```python
paths = export_paths(self.controller.project_json, output_dir)
dialog = ExportPreviewDialog(self.controller.project_json, paths, dpi, self)
if dialog.exec() != QDialog.DialogCode.Accepted:
    self.status_label.setText("已取消封面輸出。")
    return
worker = ExportWorker(self.controller.project_json, paths, dpi)
```

Completion text lists all three files on separate lines.

- [ ] **Step 5: Run desktop export tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest \
  desktop/tests/test_export_preview_dialog.py \
  desktop/tests/test_export_worker.py \
  desktop/tests/test_cover_page.py \
  desktop/tests/test_round2_desktop.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit desktop export flow**

```bash
git add \
  python/src/epub_a4_word_desktop/cover/export_preview_dialog.py \
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

**Interfaces:**
- Verifies: Android bridge still receives the same conversion API while shared pagination changes underneath it.
- Documents: exact meanings of original-size PDF, A4 print PDF, A4 DOCX, alias confirmation, and 100% print settings.

- [ ] **Step 1: Add Android bridge pagination-safety regression**

Add a bridge test that converts a long mixed CJK/Latin EPUB with `single_a5` and asserts conversion succeeds with more than one logical page and no error payload.

- [ ] **Step 2: Run Android bridge tests**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests/test_android_bridge.py -q
```

Expected: all tests pass after Tasks 1-3; any signature regression is fixed before continuing.

- [ ] **Step 3: Update user-facing documentation**

Document:

- all body modes use fixed Word line heights;
- `需確認` aliases require explicit confirmation;
- complete cover exports now produce three clearly named files;
- A4 split output is one or two pages only;
- print at 100%, disable fit-to-page/scaling;
- blank back covers require confirmation;
- old DOCX/PDF/cover projects must be regenerated to receive fixes.

- [ ] **Step 4: Commit tests and documentation**

```bash
git add \
  python-tests/test_android_bridge.py \
  README.md BUILDING.md BUILD_STATUS.md CHANGELOG.md
git commit -m "docs: explain safe body and cover export workflows"
```

---

### Task 11: Run Full Cross-Platform Verification and Build a Windows Portable Artifact

**Files:**
- Modify only if required by failing checks: `.github/workflows/desktop.yml`
- Modify only if required by failing checks: `.github/workflows/android.yml`
- Modify only if required by failing checks: `.github/workflows/windows-portable.yml`
- Modify: `desktop/tests/test_windows_portable_packaging.py` when new modules must be asserted in the source/package manifest.

**Interfaces:**
- Produces: a PR whose exact HEAD has green Desktop, Android, and Windows Portable workflows.
- Produces: a downloadable Windows Portable ZIP and SHA-256 file from that exact HEAD.

- [ ] **Step 1: Run the complete shared Python suite**

Run:

```bash
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest python-tests -q
```

Expected: zero failures.

- [ ] **Step 2: Run the complete desktop suite offscreen**

Run:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=.:python/src:app/src/main/python \
python -m pytest desktop/tests -q
```

Expected: zero failures. When local PySide6 is unavailable, run this exact suite through Desktop GitHub Actions on Windows, macOS, and Ubuntu before merging.

- [ ] **Step 3: Run compile and structural verification**

Run:

```bash
python -m compileall -q python/src app/src/main/python scripts packaging
PYTHONPATH=.:python/src:app/src/main/python python scripts/verify_project.py
```

Expected: both commands exit 0.

- [ ] **Step 4: Inspect the final diff and update packaging assertions**

Run:

```bash
git diff --check
git status --short
```

Ensure `text_metrics.py`, `export_plan.py`, `alias_decision_row.py`, and `export_preview_dialog.py` are included by the package. Add exact path assertions to `desktop/tests/test_windows_portable_packaging.py` if the current PyInstaller collection test does not cover them.

- [ ] **Step 5: Commit verification-only changes**

```bash
git add .github/workflows desktop/tests/test_windows_portable_packaging.py
git commit -m "test: verify safe export release packaging"
```

Skip this commit only when no verification or packaging file changed.

- [ ] **Step 6: Push, open a draft PR, and wait for exact-HEAD workflows**

```bash
git push -u origin agent/impl-output-overflow-alias-cover-export
```

Required workflow conclusions for the same commit SHA:

- Desktop PySide6 tests: Windows success, macOS success, Ubuntu success.
- Android debug APK: success.
- Windows portable EXE: focused tests, source smoke, compile/project verification, PyInstaller, portable-directory verification, packaged EXE smoke, ZIP/SHA upload all success.

- [ ] **Step 7: Download and independently inspect the Portable ZIP**

Verify:

```text
EPUB2A4.exe
_internal/PySide6/plugins/platforms/qwindows.dll
portable.flag
```

Extract the inner application ZIP, count files, and compare its SHA-256 to the uploaded `.sha256` report. Do not claim Microsoft Word rendering is fully confirmed until the user regenerates a DOCX from the real EPUB and checks it in Windows Word.

- [ ] **Step 8: Request code review, fix all critical/important findings, rerun exact-HEAD CI, then merge**

The final PR description must list:

- shared fixed Word text metrics;
- all five body-output modes covered;
- alias confirm/ignore behavior;
- one-or-two-page A4 cover output;
- original-size PDF;
- blank-back warning;
- exact test counts and workflow run IDs;
- the remaining real-device Word/printing caveat.

---

## Self-Review Checklist

- Every requirement in the approved specification maps to Tasks 1-11.
- The pagination and DOCX writer use one shared metrics module and the same numeric line height.
- The alias pipeline does not promote medium aliases without an explicit accepted input.
- Permanent alias caching remains delayed until a cover is selected.
- `build_print_plan()` has no `spine` page in split mode.
- PDF, DOCX, and preview all consume the same `PrintPlan`.
- The original-size PDF is separate from the A4 print PDF.
- Three-file replacement is atomic and preserves previous outputs on any failure.
- No task introduces automatic scaling, paid services, Z-Library, or image generation.
- The plan contains no unresolved placeholders or contradictory signatures.
