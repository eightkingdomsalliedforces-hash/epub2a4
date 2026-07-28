# Balanced Publisher Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace only the `reference_stacked` spine with the approved balanced publisher layout: logo alone at top, dominant vertical title, accent volume circle, lower author/code, and one publisher name at the bottom.

**Architecture:** `modern_spine_layout.py` owns deterministic tiered geometry and minimum readable type sizes; `templates.py` maps editable metadata and the real publisher logo into those slots. Every generated element uses the same `spine_rect` clipping contract across preview, raster, PDF, and DOCX, while the other two spine styles remain unchanged.

**Tech Stack:** Python 3.13, dataclasses, Pillow, shared cover model/render/export pipeline, pytest

## Global Constraints

- Change only the existing `reference_stacked` style.
- Top area contains only the selected publisher logo; no `川`, abbreviation, or generated text logo.
- Publisher name appears exactly once at the bottom.
- Main title is the largest and most prominent text.
- English title and arc label remain independently editable metadata.
- Volume number appears in a circle using the current accent color.
- Author sits in the lower section; internal code sits near the lower-left safe area.
- Width tiers are full at `>= 10 mm`, compact at `6–10 mm`, and minimal below `6 mm`.
- Compact omits English title; minimal also omits internal code and shortens the author zone.
- Every slot, circle, logo, and text element remains inside `spine_rect`.
- Logo uses `contain` and preserves its aspect ratio.
- `clean_centered` and `parallel_columns` retain their current behavior.

---

### Task 1: Tier-specific approved A geometry

**Files:**
- Modify: `python/src/epub_a4_word/cover/modern_spine_layout.py`
- Test: `python-tests/cover/test_modern_spine_layout.py`

**Interfaces:**
- Preserves: `build_modern_spine_slots(layout, style, accent) -> ModernSpineLayout`
- Produces: `_reference_full_slots`, `_reference_compact_slots`, `_reference_minimal_slots`
- Produces: `fit_spine_font_size(slot: ModernSpineSlot, text: str) -> tuple[float, tuple[str, ...]]`
- Produces reference roles:
  - full: logo, english_title, title, arc, volume_badge, author, code, publisher
  - compact: logo, title, arc, volume_badge, author, code, publisher
  - minimal: logo, title, arc, volume_badge, author, publisher

- [ ] **Step 1: Replace generic role expectations with tier expectations**

```python
@pytest.mark.parametrize(
    ("width", "tier", "roles"),
    [
        (
            12.0,
            "full",
            {"logo", "english_title", "title", "arc", "volume_badge", "author", "code", "publisher"},
        ),
        (
            8.0,
            "compact",
            {"logo", "title", "arc", "volume_badge", "author", "code", "publisher"},
        ),
        (
            4.0,
            "minimal",
            {"logo", "title", "arc", "volume_badge", "author", "publisher"},
        ),
    ],
)
def test_reference_spine_degrades_by_width(width, tier, roles, sample_project) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=width)),
        "reference_stacked",
        "#DF6B32",
    )
    assert result.tier == tier
    assert {slot.role for slot in result.slots} == roles
```

- [ ] **Step 2: Run the tier test and verify failure**

Run: `python -m pytest python-tests/cover/test_modern_spine_layout.py -k degrades -q`

Expected: FAIL because all reference tiers currently return the same roles.

- [ ] **Step 3: Implement explicit A-layout tier builders**

Use non-overlapping fractions within `spine_safe_rect`:

```python
def _reference_full_slots(safe, tier, accent):
    return (
        _slot(safe, tier, "logo", 0.00, 0.10, accent),
        _slot(safe, tier, "english_title", 0.11, 0.08, "#444444", direction="horizontal"),
        _slot(safe, tier, "title", 0.20, 0.35, "#191919", weight=700),
        _slot(safe, tier, "arc", 0.56, 0.07, accent, weight=600),
        _slot(safe, tier, "volume_badge", 0.64, 0.09, accent, weight=700),
        _slot(safe, tier, "author", 0.75, 0.11, "#191919", weight=500),
        _slot(safe, tier, "code", 0.87, 0.05, "#555555", left=0.00, width=0.52, direction="horizontal"),
        _slot(safe, tier, "publisher", 0.93, 0.06, "#191919", weight=500, direction="horizontal"),
    )
```

Create compact and minimal builders with the required omitted roles and give
their recovered height to `title`. Route `_reference_slots` by `tier`. Keep
the existing `clean` and `parallel` builders byte-for-byte except for imports
or shared helper signatures.

- [ ] **Step 4: Assert prominence, ordering, and non-overlap**

```python
def test_reference_spine_title_is_dominant_and_publisher_is_last(sample_project) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=12.0)),
        "reference_stacked",
        "#DF6B32",
    )
    slots = {slot.role: slot for slot in result.slots}
    assert slots["title"].font_size_pt > slots["author"].font_size_pt
    assert slots["title"].font_size_pt > slots["publisher"].font_size_pt
    assert slots["logo"].rect.bottom_mm <= slots["english_title"].rect.y_mm
    assert slots["publisher"].rect.bottom_mm <= calculate_layout(
        sample_project(manual_spine_width_mm=12.0)
    ).spine_rect.bottom_mm


def test_long_reference_title_fits_without_dropping_below_readable_minimum(
    sample_project,
) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=8.0)),
        "reference_stacked",
        "#DF6B32",
    )
    title = next(slot for slot in result.slots if slot.role == "title")
    fitted, warnings = fit_spine_font_size(
        title,
        "歡迎來到實力至上主義的教室二年級篇",
    )
    assert fitted >= 6.0
    assert fitted <= title.font_size_pt
    assert isinstance(warnings, tuple)
```

Retain the parameterized boundary test at widths `4.0`, `6.03`, `8.0`, and
`12.0`, and add pairwise vertical non-overlap assertions for slots which span
the full width.

Implement `fit_spine_font_size` with CJK full-width units and Latin
half-width units. Reduce in 0.5 pt steps to role minimums
`title=6.0`, `author=4.5`, `publisher=4.0`, `code=3.5`; when the minimum still
needs wrapping, retain the minimum, let the bounded text rectangle wrap, and
return the warning `("書脊文字已縮至可讀下限並限制於安全範圍。",)`.

- [ ] **Step 5: Run layout tests**

Run: `python -m pytest python-tests/cover/test_modern_spine_layout.py -q`

Expected: PASS.

- [ ] **Step 6: Commit geometry**

```bash
git add python/src/epub_a4_word/cover/modern_spine_layout.py python-tests/cover/test_modern_spine_layout.py
git commit -m "feat: redesign balanced reference spine geometry"
```

---

### Task 2: Metadata mapping, logo-only top, and accent badge

**Files:**
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Test: `python-tests/cover/test_modern_spine_template.py`

**Interfaces:**
- Consumes existing editable fields: `title`, `english_title`, `arc_label`, `volume_number`, `author`, `internal_book_code`, `publisher`, `publisher_logo`, `spine_accent_color`
- Produces one element per available slot and exactly one publisher text element.
- Keeps `fit="contain"` and `clip_to_region=True` on the logo.

- [ ] **Step 1: Write failing content-count and logo purity tests**

```python
def test_reference_spine_top_contains_only_real_logo(sample_project, tmp_path) -> None:
    project = _modern_project(sample_project, 12.0, "reference_stacked", tmp_path)
    result = apply_template(project, "modern_vertical_back_with_spine")
    logo = result.elements_by_id["modern-spine-logo"]
    assert logo.kind == ElementKind.IMAGE
    assert logo.content["fit"] == "contain"
    assert logo.content["clip_to_region"] is True
    assert all(
        element.id != "modern-spine-publisher-abbreviation"
        for element in result.elements
    )


def test_reference_spine_has_one_publisher_name_at_bottom(sample_project, tmp_path) -> None:
    result = apply_template(
        _modern_project(sample_project, 12.0, "reference_stacked", tmp_path),
        "modern_vertical_back_with_spine",
    )
    publisher_elements = [
        element
        for element in result.elements
        if element.content.get("layout_role") == "publisher"
    ]
    assert [element.id for element in publisher_elements] == ["modern-spine-publisher"]


def test_missing_logo_never_creates_text_logo_and_reports_warning(
    sample_project,
    tmp_path,
) -> None:
    project = _modern_project(sample_project, 8.0, "reference_stacked", tmp_path)
    project = replace(
        project,
        metadata=replace(project.metadata, publisher_logo=None),
    )
    result = apply_template(project, "modern_vertical_back_with_spine")
    assert "modern-spine-logo" not in result.elements_by_id
    assert not any("abbreviation" in element.id for element in result.elements)
    title = result.elements_by_id["modern-spine-title"]
    assert "出版社 Logo" in " ".join(title.content["layout_warnings"])
```

- [ ] **Step 2: Run the new template tests**

Run: `python -m pytest python-tests/cover/test_modern_spine_template.py -k "logo or one_publisher" -q`

Expected: The purity assertions document the approved contract; any duplicate
or derived publisher text fails.

- [ ] **Step 3: Map only supplied editable metadata**

Keep the existing `values` mapping, but do not derive fallback letters from
publisher name or logo filename. Skip an empty slot rather than producing
placeholder text. Give `publisher` horizontal direction at the bottom and
retain vertical directions for Chinese title, arc, and author.

Call `fit_spine_font_size(slot, value)` before `text_element`; use the returned
size and merge its warnings into `layout_warnings`. If the logo file is
missing, add `出版社 Logo 無法讀取，已略過 Logo。` to the title element’s
warnings and do not create any replacement text element.

For the logo, keep:

```python
content={
    "path": logo.path,
    "fit": "contain",
    "group_id": "modern-spine-stack",
    "layout_role": "logo",
    "clip_to_region": True,
}
```

- [ ] **Step 4: Make the volume circle use the active accent exactly**

```python
def test_volume_badge_uses_current_accent_color(sample_project, tmp_path) -> None:
    project = _modern_project(sample_project, 12.0, "reference_stacked", tmp_path)
    project = replace(
        project,
        metadata=replace(project.metadata, spine_accent_color="#4A78C2"),
    )
    result = apply_template(project, "modern_vertical_back_with_spine")
    badge = result.elements_by_id["modern-spine-volume-badge"]
    number = result.elements_by_id["modern-spine-volume"]
    assert badge.content["stroke"] == "#4A78C2"
    assert number.content["color"] == "#4A78C2"
```

Keep diameter as `min(width, height)`, center it in the slot, and assert both
the shape and number transforms are within `spine_rect`.

- [ ] **Step 5: Test width degradation against generated elements**

```python
@pytest.mark.parametrize(
    ("width", "missing_ids"),
    [
        (12.0, set()),
        (8.0, {"modern-spine-english-title"}),
        (4.0, {"modern-spine-english-title", "modern-spine-code"}),
    ],
)
def test_reference_generated_elements_follow_width_tier(
    width, missing_ids, sample_project, tmp_path
) -> None:
    result = apply_template(
        _modern_project(sample_project, width, "reference_stacked", tmp_path),
        "modern_vertical_back_with_spine",
    )
    assert missing_ids.isdisjoint(result.elements_by_id)
```

- [ ] **Step 6: Run template and metadata tests**

Run: `python -m pytest python-tests/cover/test_modern_spine_template.py python-tests/cover/test_templates.py python-tests/cover/test_template_metadata_refresh.py -q`

Expected: PASS; all three title-related fields remain independently editable.

- [ ] **Step 7: Commit metadata rendering**

```bash
git add python/src/epub_a4_word/cover/templates.py python-tests/cover/test_modern_spine_template.py
git commit -m "feat: render approved publisher spine content"
```

---

### Task 3: Cross-export clipping and visual regression

**Files:**
- Modify: `python-tests/cover/test_modern_cover_reference.py`
- Modify: `python-tests/cover/test_pdf_export.py`
- Modify: `python-tests/cover/test_docx_export.py`
- Modify: `scripts/inspect_cover_exports.py`

**Interfaces:**
- Consumes the shared generated spine elements from Tasks 1–2.
- Verifies raster preview, PDF, and DOCX export use the same bounded layout.

- [ ] **Step 1: Add shared element-bound assertions for all width tiers**

```python
@pytest.mark.parametrize("width", [4.0, 6.03, 8.0, 12.0])
def test_reference_spine_export_elements_are_inside_real_spine(
    width, sample_project, tmp_path
) -> None:
    project = apply_template(
        _modern_project(sample_project, width, "reference_stacked", tmp_path),
        "modern_vertical_back_with_spine",
    )
    spine = calculate_layout(project).spine_rect
    for element in project.elements:
        if not element.id.startswith("modern-spine-"):
            continue
        assert spine.x_mm <= element.transform.x_mm
        assert element.transform.x_mm + element.transform.width_mm <= spine.right_mm
        assert spine.y_mm <= element.transform.y_mm
        assert element.transform.y_mm + element.transform.height_mm <= spine.bottom_mm
```

- [ ] **Step 2: Export and inspect one full-tier reference project**

Use a 12 mm spine with all metadata populated and a rectangular logo. Export
preview PNG, PDF, and DOCX through the public service. Assert:

- every output file is non-empty;
- PNG dimensions match the reported render dimensions;
- PDF mediabox equals the full spread;
- DOCX reopens and has the expected drawing count;
- no export path creates an element named with `publisher-abbreviation`.

- [ ] **Step 3: Add script diagnostics for the A-layout roles**

Extend `scripts/inspect_cover_exports.py` to print, for each modern spine
element:

```text
id, layout_role, x_mm, y_mm, width_mm, height_mm, inside_spine
```

Exit non-zero when `inside_spine` is false or when more than one
`layout_role=publisher` appears.

- [ ] **Step 4: Run cover export verification**

Run: `python -m pytest python-tests/cover/test_modern_spine_layout.py python-tests/cover/test_modern_spine_template.py python-tests/cover/test_modern_cover_reference.py python-tests/cover/test_pdf_export.py python-tests/cover/test_docx_export.py -q`

Run: `python scripts/inspect_cover_exports.py --help`

Expected: PASS and exit code 0.

- [ ] **Step 5: Commit cross-export coverage**

```bash
git add python-tests/cover/test_modern_cover_reference.py python-tests/cover/test_pdf_export.py python-tests/cover/test_docx_export.py scripts/inspect_cover_exports.py
git commit -m "test: verify balanced spine across cover exports"
```
