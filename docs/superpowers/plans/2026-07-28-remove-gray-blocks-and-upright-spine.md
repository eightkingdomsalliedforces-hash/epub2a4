# Remove Gray Blocks and Keep Spine Text Upright Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the obsolete gray-block cover template and migrate its old projects while keeping every non-English spine field upright.

**Architecture:** The shared template catalog remains the source of available templates, while `loads_project` performs a narrow compatibility migration for the two removed element IDs and the removed active-template value. Modern spine slots continue to own text direction: only `english_title` is horizontal/rotated, and title, arc, volume, author, code, and publisher are vertical/upright. Desktop selectors consume the same reduced option set explicitly.

**Tech Stack:** Python 3.13, dataclasses, Pillow, python-docx, pypdf, PySide6, pytest, pytest-qt

## Global Constraints

- Remove `top_bottom_blocks` from every shared and Desktop template list.
- Never generate `template-front-top-block` or `template-back-bottom-block`.
- Loading an old `.cover.json` removes those two IDs and maps `background.active_template = "top_bottom_blocks"` to `"minimal_text"`.
- Preserve unrelated user-created shape and image elements.
- Chinese, digits, mixed Chinese/digits, author, publisher, volume, and internal book code remain upright.
- Only the independent pure-English title field may rotate 90 degrees.
- Every spine element remains bounded by the physical spine.
- PNG, PDF, and DOCX must not contain the removed gray blocks.

---

### Task 1: Remove the gray-block template and migrate old projects

**Files:**
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `python-tests/cover/test_templates.py`
- Test: `python-tests/cover/test_project_io.py`
- Test: `python-tests/cover/test_user_reported_cover_regressions.py`
- Test: `desktop/tests/test_user_reported_cover_regressions.py`

**Interfaces:**
- Produces: `REMOVED_TEMPLATE_ELEMENT_IDS = frozenset({"template-front-top-block", "template-back-bottom-block"})`
- Produces: `_migrate_removed_template_artifacts(project: CoverProject) -> CoverProject`
- Changes: `list_templates()` no longer returns `top_bottom_blocks`.
- Changes: `apply_template(project, "top_bottom_blocks")` raises the existing unknown-template `ValueError`.

- [ ] **Step 1: Write failing shared catalog and migration tests**

Update the expected catalog in `python-tests/cover/test_templates.py`:

```python
def test_template_catalog_omits_removed_gray_block_template(
    sample_project,
) -> None:
    assert [item.id for item in list_templates()] == [
        "minimal_text",
        "front_image_plain_back",
        "full_spread",
        "publisher_back_matter_with_spine",
        "modern_vertical_back_with_spine",
    ]
    with pytest.raises(ValueError):
        apply_template(sample_project(), "top_bottom_blocks")
```

Add to `python-tests/cover/test_project_io.py`:

```python
def test_loads_project_removes_legacy_gray_blocks_but_keeps_user_shapes(
    sample_project,
) -> None:
    legacy = replace(
        sample_project(),
        background={"active_template": "top_bottom_blocks"},
        elements=(
            _shape("template-front-top-block", Region.FRONT, "#E2E2E2"),
            _shape("template-back-bottom-block", Region.BACK, "#E2E2E2"),
            _shape("user-decoration", Region.BACK, "#123456"),
        ),
    )

    restored = loads_project(dumps_project(legacy))

    assert restored.background["active_template"] == "minimal_text"
    assert set(restored.elements_by_id) == {"user-decoration"}
```

Define `_shape` in the test file with a real `CoverElement`, `ElementTransform(1, 1, 10, 10)`, and `ElementKind.SHAPE`; do not mock serialization.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests\cover\test_templates.py python-tests\cover\test_project_io.py -k "gray_block or removed_gray" -q
```

Expected: FAIL because the catalog still exposes the template and `loads_project` preserves its elements.

- [ ] **Step 3: Implement the narrow load migration**

In `project_io.py`, add after JSON-to-model construction:

```python
REMOVED_TEMPLATE_ELEMENT_IDS = frozenset(
    {"template-front-top-block", "template-back-bottom-block"}
)


def _migrate_removed_template_artifacts(project: CoverProject) -> CoverProject:
    background = dict(project.background)
    if background.get("active_template") == "top_bottom_blocks":
        background["active_template"] = "minimal_text"
    elements = tuple(
        element
        for element in project.elements
        if element.id not in REMOVED_TEMPLATE_ELEMENT_IDS
    )
    return replace(project, background=background, elements=elements)
```

Import `replace` from `dataclasses`, then change `loads_project` to call this function before validation:

```python
project = _migrate_removed_template_artifacts(_project_from_dict(raw))
validate_project(project)
return project
```

Do not remove any other `template-*` or user shape IDs during loading.

- [ ] **Step 4: Remove the builder, catalog entry, and Desktop choices**

Delete the `TemplateSummary("top_bottom_blocks", ...)` entry, `_top_bottom_blocks`, and the `_BUILDERS["top_bottom_blocks"]` entry from `templates.py`.

Remove these two UI additions:

```python
self.template_combo.addItem("上下色塊", "top_bottom_blocks")
```

from `setup_panel.py`, and:

```python
("上下色塊", "top_bottom_blocks"),
```

from `TemplatePanel` in `cover_page.py`.

Update parameterized template tests and the legacy-alias regression so they no longer treat `top_bottom_blocks` as supported.

- [ ] **Step 5: Add and run Desktop selector tests**

Change `desktop/tests/test_user_reported_cover_regressions.py`:

```python
expected = [
    "minimal",
    "full_bleed_image",
    "classic_book",
    "publisher_back_matter",
    "modern_vertical_back_with_spine",
]
assert _combo_values(setup.template_combo) == expected
assert _combo_values(toolbar.combo) == expected
assert "top_bottom_blocks" not in expected
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests\cover\test_templates.py python-tests\cover\test_project_io.py python-tests\cover\test_user_reported_cover_regressions.py desktop\tests\test_user_reported_cover_regressions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit template removal and migration**

```powershell
git add python/src/epub_a4_word/cover/templates.py python/src/epub_a4_word/cover/project_io.py python/src/epub_a4_word_desktop/cover/setup_panel.py python/src/epub_a4_word_desktop/pages/cover_page.py python-tests/cover/test_templates.py python-tests/cover/test_project_io.py python-tests/cover/test_user_reported_cover_regressions.py desktop/tests/test_user_reported_cover_regressions.py
git commit -m "fix: remove hidden gray cover blocks"
```

---

### Task 2: Keep non-English spine fields upright

**Files:**
- Modify: `python/src/epub_a4_word/cover/modern_spine_layout.py`
- Test: `python-tests/cover/test_modern_spine_layout.py`
- Test: `python-tests/cover/test_modern_spine_template.py`

**Interfaces:**
- Consumes: `ModernSpineSlot.direction`
- Produces directions:
  - `english_title`: `"horizontal"`
  - `title`, `arc`, `volume_badge`, `author`, `code`, `publisher`: `"vertical"`
- Existing template rendering contract remains: horizontal means `rotation_deg=90.0`; vertical means `rotation_deg=0.0`.

- [ ] **Step 1: Write failing slot-direction tests**

Add to `python-tests/cover/test_modern_spine_layout.py`:

```python
def test_only_english_title_uses_rotated_spine_direction(sample_project) -> None:
    result = build_modern_spine_slots(
        calculate_layout(sample_project(manual_spine_width_mm=12.0)),
        "reference_stacked",
        "#DF6B32",
    )
    directions = {slot.role: slot.direction for slot in result.slots}
    assert directions["english_title"] == "horizontal"
    assert {
        role
        for role, direction in directions.items()
        if role != "logo" and direction == "horizontal"
    } == {"english_title"}
```

Add to `python-tests/cover/test_modern_spine_template.py`:

```python
def test_chinese_digits_author_code_and_publisher_are_upright(
    sample_project, tmp_path
) -> None:
    project = _modern_project(
        sample_project, 12.0, "reference_stacked", tmp_path
    )
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            title="科學超電磁炮A",
            arc_label="冬川篇",
            volume_number="01",
            author="鎌池和馬",
            internal_book_code="CL0308-17",
            publisher="台灣角川",
        ),
    )
    result = apply_template(project, "modern_vertical_back_with_spine")

    assert result.elements_by_id["modern-spine-english-title"].transform.rotation_deg == 90.0
    for element_id in (
        "modern-spine-title",
        "modern-spine-arc",
        "modern-spine-volume",
        "modern-spine-author",
        "modern-spine-code",
        "modern-spine-publisher",
    ):
        assert result.elements_by_id[element_id].transform.rotation_deg == 0.0
```

- [ ] **Step 2: Run the direction tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests\cover\test_modern_spine_layout.py python-tests\cover\test_modern_spine_template.py -k "only_english or upright" -q
```

Expected: FAIL because `code` and `publisher` currently use horizontal direction.

- [ ] **Step 3: Make only the English title horizontal**

In all three reference tier builders in `modern_spine_layout.py`, remove
`direction="horizontal"` from the `code` and `publisher` slots. Keep it only
on `english_title`. Do not change slot geometry, font fitting, width tiers,
or clipping.

- [ ] **Step 4: Run complete modern-spine tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests\cover\test_modern_spine_layout.py python-tests\cover\test_modern_spine_template.py python-tests\cover\test_modern_cover_reference.py -q
```

Expected: PASS, including all element-bound assertions.

- [ ] **Step 5: Commit the direction fix**

```powershell
git add python/src/epub_a4_word/cover/modern_spine_layout.py python-tests/cover/test_modern_spine_layout.py python-tests/cover/test_modern_spine_template.py
git commit -m "fix: keep spine metadata upright"
```

---

### Task 3: Verify all preview and export paths

**Files:**
- Modify: `python-tests/cover/test_user_reported_cover_regressions.py`
- Modify: `python-tests/cover/test_modern_cover_reference.py`
- Verify: `python/src/epub_a4_word/cover/render.py`
- Verify: `python/src/epub_a4_word/cover/pdf_export.py`
- Verify: `python/src/epub_a4_word/cover/docx_export.py`

**Interfaces:**
- Consumes the migrated project from `loads_project`.
- Verifies raster preview, PDF, and DOCX receive no removed gray-block elements.

- [ ] **Step 1: Write the cross-export regression**

Create a legacy project payload with both removed block IDs and one
`user-decoration` shape, round-trip it through `loads_project`, then:

```python
def test_legacy_gray_blocks_do_not_reach_preview_pdf_or_docx(
    legacy_gray_project_json, tmp_path
) -> None:
    project = loads_project(legacy_gray_project_json)
    assert "template-front-top-block" not in project.elements_by_id
    assert "template-back-bottom-block" not in project.elements_by_id
    assert "user-decoration" in project.elements_by_id

    preview = render_spread(project, 200)
    preview_path = tmp_path / "preview.png"
    preview.save(preview_path)
    pdf = export_original_pdf(project, tmp_path / "cover.pdf", dpi=200).path
    docx = export_docx(project, tmp_path / "cover.docx").path

    assert preview_path.stat().st_size > 0
    assert pdf.stat().st_size > 0
    assert docx.stat().st_size > 0
    assert all(
        element.id not in {
            "template-front-top-block",
            "template-back-bottom-block",
        }
        for element in project.elements
    )
```

Use the real public render/export functions and reuse the Task 1 fixture
helper; do not inspect mocks.

- [ ] **Step 2: Run focused cover export tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests\cover\test_user_reported_cover_regressions.py python-tests\cover\test_modern_cover_reference.py python-tests\cover\test_pdf_export.py python-tests\cover\test_docx_export.py -q
```

Expected: PASS.

- [ ] **Step 3: Run all Python and Desktop tests separately**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests -q
.\.venv\Scripts\python.exe -m pytest desktop\tests -q
```

Expected: both exit 0. Keep the suites separate because they contain
same-named test modules.

- [ ] **Step 4: Run source and project checks**

Run:

```powershell
git diff --check origin/main...HEAD
.\.venv\Scripts\python.exe scripts\verify_project.py
git status --short
```

Expected: no whitespace errors; project verification passes; only the known
local-only `local.properties` and `uv.lock` may remain untracked.

- [ ] **Step 5: Commit cross-export coverage**

```powershell
git add python-tests/cover/test_user_reported_cover_regressions.py python-tests/cover/test_modern_cover_reference.py
git commit -m "test: prevent hidden gray blocks in exports"
```
