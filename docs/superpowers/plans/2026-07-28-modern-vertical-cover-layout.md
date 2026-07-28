# Modern Vertical Cover Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent modern vertical back-cover template, three selectable adaptive spine styles, deterministic cover-derived accent colours, and a shared full trim frame for preview, DOCX, and PDF on Desktop and Android.

**Architecture:** Extend the shared Python cover metadata and template core first, then add focused layout modules for accent extraction, vertical copy, modern spines, and crop-frame geometry. Desktop and Android only collect/edit the shared fields; all placement and colour decisions remain in Python. Raster preview/PDF and editable DOCX consume the same template elements and crop-frame coordinates.

**Tech Stack:** Python 3.13, Pillow, python-docx/VML OOXML, PySide6, Kotlin, Jetpack Compose, Chaquopy, pytest, JUnit, Gradle, PyInstaller.

## Global Constraints

- New template ID is exactly `modern_vertical_back_with_spine`; existing `publisher_back_matter_with_spine` remains unchanged.
- Spine styles are exactly `reference_stacked`, `clean_centered`, and `parallel_columns`; default is `reference_stacked`.
- Accent modes are exactly `auto` and `manual`; fallback colour is exactly `#F15A24`.
- `back_vertical_copy` defaults from source `description` only when a project is first created; `back_highlight_copy` defaults empty.
- Full crop-frame line width is exactly `0.35 pt`; `show_crop_marks` controls every preview and export consumer.
- No cover, back-cover, spine, Logo, barcode, text, or crop-frame rectangle may extend beyond its assigned geometry.
- The reference image’s bottom silhouettes, grade number, and English decoration are not generated.
- Desktop and Android must expose the same editable fields and use the same shared Python layout core.
- Existing schema-v1 projects load without migration failure.
- Release version is `v0.7.0`, Android `versionCode` becomes `8`, and release assets remain Android APK, Windows Portable ZIP, and `SHA256SUMS.txt`.

---

### Task 1: Persist Modern Template Metadata Across Python and Android

**Files:**
- Modify: `python/src/epub_a4_word/cover/models.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/model/CoverModels.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/model/CoverProjectJson.kt`
- Test: `python-tests/cover/test_project_io.py`
- Test: `python-tests/cover/test_service.py`
- Test: `app/src/test/java/tw/daniel/epubword/cover/model/CoverProjectJsonTest.kt`

**Interfaces:**
- Produces Python `CoverMetadata.back_vertical_copy: str`, `back_highlight_copy: str`, `spine_style: str`, `accent_color_mode: str`, and `extracted_accent_color: str`.
- Produces matching Kotlin `CoverMetadata` camel-case properties and JSON keys.
- Later tasks consume these fields without adding template state to `background`.

- [ ] **Step 1: Write failing Python persistence and default tests**

```python
def test_modern_metadata_round_trips(sample_project):
    metadata = replace(
        sample_project().metadata,
        back_vertical_copy="黑色直排內文",
        back_highlight_copy="醒目文案",
        spine_style="parallel_columns",
        accent_color_mode="manual",
        extracted_accent_color="#336699",
    )
    reopened = loads_project(dumps_project(replace(sample_project(), metadata=metadata)))
    assert reopened.metadata.back_vertical_copy == "黑色直排內文"
    assert reopened.metadata.back_highlight_copy == "醒目文案"
    assert reopened.metadata.spine_style == "parallel_columns"
    assert reopened.metadata.accent_color_mode == "manual"
    assert reopened.metadata.extracted_accent_color == "#336699"


def test_old_project_defaults_modern_metadata(old_project_json):
    metadata = loads_project(old_project_json).metadata
    assert metadata.back_vertical_copy == ""
    assert metadata.back_highlight_copy == ""
    assert metadata.spine_style == "reference_stacked"
    assert metadata.accent_color_mode == "auto"
    assert metadata.extracted_accent_color == ""
```

- [ ] **Step 2: Run Python tests and verify RED**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_project_io.py python-tests/cover/test_service.py -q
```

Expected: failures report unknown/missing `CoverMetadata` fields.

- [ ] **Step 3: Add Python fields, JSON keys, validation, and creation defaults**

Add to `CoverMetadata`:

```python
back_vertical_copy: str = ""
back_highlight_copy: str = ""
spine_style: str = "reference_stacked"
accent_color_mode: str = "auto"
extracted_accent_color: str = ""
```

Add all five keys to `_validate_metadata`, `_metadata_from_dict`, and service setting allowlists. Validate exact enum-like values:

```python
if metadata.spine_style not in {
    "reference_stacked", "clean_centered", "parallel_columns"
}:
    raise CoverValidationError("metadata.spine_style 無效。")
if metadata.accent_color_mode not in {"auto", "manual"}:
    raise CoverValidationError("metadata.accent_color_mode 無效。")
```

In `new_project`, use source description only when the caller did not send `back_vertical_copy`:

```python
back_vertical_copy=metadata_text(
    "back_vertical_copy", inspection.metadata.description
),
back_highlight_copy=metadata_text("back_highlight_copy", ""),
spine_style=metadata_text("spine_style", "reference_stacked"),
accent_color_mode=metadata_text("accent_color_mode", "auto"),
extracted_accent_color=metadata_text("extracted_accent_color", ""),
```

- [ ] **Step 4: Write failing Kotlin JSON round-trip tests**

```kotlin
@Test
fun modernCoverMetadataRoundTrips() {
    val metadata = CoverMetadata(
        backVerticalCopy = "黑色直排內文",
        backHighlightCopy = "醒目文案",
        spineStyle = "clean_centered",
        accentColorMode = "manual",
        extractedAccentColor = "#336699",
    )
    val decoded = CoverProjectJson.decode(
        CoverProjectJson.encode(project(metadata = metadata)),
    )
    assertEquals(metadata, decoded.metadata)
}
```

- [ ] **Step 5: Add matching Kotlin fields and JSON mappings**

```kotlin
val backVerticalCopy: String = "",
val backHighlightCopy: String = "",
val spineStyle: String = "reference_stacked",
val accentColorMode: String = "auto",
val extractedAccentColor: String = "",
```

Map them to `back_vertical_copy`, `back_highlight_copy`, `spine_style`, `accent_color_mode`, and `extracted_accent_color` in both decode and encode paths.

- [ ] **Step 6: Run focused Python and Android model tests**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_project_io.py python-tests/cover/test_service.py -q
gradle --no-daemon :app:testDebugUnitTest --tests "tw.daniel.epubword.cover.model.CoverProjectJsonTest"
```

Expected: both commands pass.

- [ ] **Step 7: Commit**

```powershell
git add python/src/epub_a4_word/cover/models.py python/src/epub_a4_word/cover/project_io.py python/src/epub_a4_word/cover/service.py app/src/main/java/tw/daniel/epubword/cover/model/CoverModels.kt app/src/main/java/tw/daniel/epubword/cover/model/CoverProjectJson.kt python-tests/cover/test_project_io.py python-tests/cover/test_service.py app/src/test/java/tw/daniel/epubword/cover/model/CoverProjectJsonTest.kt
git commit -m "feat: persist modern cover metadata"
```

### Task 2: Extract a Deterministic Accessible Accent Colour

**Files:**
- Create: `python/src/epub_a4_word/cover/accent_color.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Test: `python-tests/cover/test_accent_color.py`
- Test: `python-tests/cover/test_service.py`

**Interfaces:**
- Produces `extract_accent_color(path: Path | str) -> str`.
- Produces `apply_auto_accent(metadata: CoverMetadata, path: Path | str | None) -> tuple[CoverMetadata, tuple[str, ...]]`.
- Template builders read only `metadata.spine_accent_color`; they do not perform image analysis.

- [ ] **Step 1: Write failing deterministic colour tests**

```python
def test_extracts_dominant_saturated_colour(tmp_path):
    path = tmp_path / "cover.png"
    image = Image.new("RGB", (100, 100), "#F7F7F7")
    ImageDraw.Draw(image).rectangle((0, 0, 69, 99), fill="#2674D9")
    image.save(path)
    assert extract_accent_color(path) == "#2674D9"


def test_ignores_black_white_and_gray(tmp_path):
    path = tmp_path / "cover.png"
    image = Image.new("RGB", (90, 30))
    image.paste("#FFFFFF", (0, 0, 30, 30))
    image.paste("#111111", (30, 0, 60, 30))
    image.paste("#E85D2A", (60, 0, 90, 30))
    image.save(path)
    assert extract_accent_color(path) == "#E85D2A"


def test_manual_accent_is_not_overwritten(tmp_path):
    metadata = CoverMetadata(
        spine_accent_color="#225588",
        accent_color_mode="manual",
    )
    updated, warnings = apply_auto_accent(metadata, tmp_path / "missing.png")
    assert updated.spine_accent_color == "#225588"
    assert warnings == ()
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_accent_color.py -q
```

Expected: import failure for `accent_color`.

- [ ] **Step 3: Implement fixed quantization and contrast correction**

Implement these public functions:

```python
FALLBACK_ACCENT = "#F15A24"


def extract_accent_color(path: Path | str) -> str:
    with Image.open(path) as source:
        rgb = ImageOps.exif_transpose(source).convert("RGB")
        rgb.thumbnail((128, 128), Image.Resampling.LANCZOS)
        quantized = rgb.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette() or []
        candidates = []
        for count, index in quantized.getcolors() or []:
            r, g, b = palette[index * 3:index * 3 + 3]
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.25 or v < 0.18 or v > 0.95:
                continue
            candidates.append((count * (0.5 + s), (r, g, b)))
        if not candidates:
            return FALLBACK_ACCENT
        rgb_value = max(candidates, key=lambda item: item[0])[1]
        return _ensure_white_contrast(rgb_value, minimum_ratio=3.0)
```

`_ensure_white_contrast` repeatedly multiplies HSV value by `0.92` until WCAG relative-luminance contrast with white is at least `3.0`, then returns uppercase `#RRGGBB`.

Implement mode handling:

```python
def apply_auto_accent(metadata, path):
    if metadata.accent_color_mode == "manual":
        return metadata, ()
    if path is None:
        return replace(
            metadata,
            spine_accent_color=FALLBACK_ACCENT,
            extracted_accent_color=FALLBACK_ACCENT,
        ), ()
    try:
        color = extract_accent_color(path)
    except (OSError, ValueError) as exc:
        return replace(
            metadata,
            spine_accent_color=FALLBACK_ACCENT,
            extracted_accent_color=FALLBACK_ACCENT,
        ), (f"無法從封面擷取主題色：{exc}",)
    return replace(
        metadata,
        spine_accent_color=color,
        extracted_accent_color=color,
    ), ()
```

- [ ] **Step 4: Wire extraction after source-cover asset discovery**

In `service.new_project`, identify the selected front-cover path from the copied `front_asset`, call `apply_auto_accent`, replace `project.metadata`, and append returned warnings to `background["warnings"]`. In `refresh_template_metadata`, accept manual colour edits by setting `accent_color_mode="manual"` only when the submitted colour differs from `extracted_accent_color`.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_accent_color.py python-tests/cover/test_service.py python-tests/cover/test_template_metadata_refresh.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add python/src/epub_a4_word/cover/accent_color.py python/src/epub_a4_word/cover/service.py python/src/epub_a4_word/cover/templates.py python-tests/cover/test_accent_color.py python-tests/cover/test_service.py python-tests/cover/test_template_metadata_refresh.py
git commit -m "feat: derive accessible cover accent color"
```

### Task 3: Lay Out Editable Multi-Column Vertical Back-Cover Copy

**Files:**
- Create: `python/src/epub_a4_word/cover/vertical_copy_layout.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word/cover/ooxml.py`
- Modify: `python/src/epub_a4_word/cover/docx_export.py`
- Test: `python-tests/cover/test_vertical_copy_layout.py`
- Test: `python-tests/cover/test_modern_back_template.py`
- Test: `python-tests/cover/test_render.py`
- Test: `python-tests/cover/test_docx_export.py`

**Interfaces:**
- Produces `VerticalColumn(text: str, rect: RectMm, font_size_pt: float)` and `VerticalCopyLayout(columns, separators, warnings)`.
- Produces `layout_vertical_copy(text, rect, *, preferred_font_pt, minimum_font_pt, preferred_gap_mm, maximum_columns)`.
- Template emits stable IDs `modern-back-copy-column-N`, `modern-back-copy-separator-N`, and `modern-back-highlight-column-N`.

- [ ] **Step 1: Write failing column layout tests**

```python
def test_vertical_copy_runs_right_to_left_without_overflow():
    target = RectMm(20, 40, 82, 110)
    result = layout_vertical_copy(
        "第一欄文字。第二欄文字。第三欄文字。",
        target,
        preferred_font_pt=10.0,
        minimum_font_pt=7.0,
        preferred_gap_mm=2.0,
        maximum_columns=10,
    )
    assert len(result.columns) >= 2
    assert all(
        target.x_mm <= column.rect.x_mm
        and column.rect.right_mm <= target.right_mm
        and target.y_mm <= column.rect.y_mm
        and column.rect.bottom_mm <= target.bottom_mm
        for column in result.columns
    )
    assert [c.rect.x_mm for c in result.columns] == sorted(
        (c.rect.x_mm for c in result.columns), reverse=True
    )


def test_vertical_copy_warns_instead_of_truncating():
    result = layout_vertical_copy(
        "字" * 1000,
        RectMm(0, 0, 30, 40),
        preferred_font_pt=10,
        minimum_font_pt=7,
        preferred_gap_mm=1,
        maximum_columns=4,
    )
    assert "".join(column.text for column in result.columns) == "字" * 1000
    assert result.warnings == ("封底直排內文超出可用範圍。",)
```

- [ ] **Step 2: Run layout tests and verify RED**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_vertical_copy_layout.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement the fitting loop**

Create immutable models:

```python
@dataclass(frozen=True)
class VerticalColumn:
    text: str
    rect: RectMm
    font_size_pt: float


@dataclass(frozen=True)
class VerticalCopyLayout:
    columns: tuple[VerticalColumn, ...]
    separators: tuple[RectMm, ...]
    warnings: tuple[str, ...]
```

For each candidate font size from preferred down to minimum in `0.5 pt` steps:

1. Convert point size to millimetres with `font_pt / 72 * 25.4`.
2. Derive character capacity from target height.
3. Respect explicit newlines as forced column breaks.
4. Place columns from `rect.right_mm` toward `rect.x_mm`.
5. Reduce gap down to `0.8 mm`.
6. Return the first fit; if none fits, return every character in overflow columns plus the warning.

- [ ] **Step 4: Write failing modern back template tests**

```python
def test_modern_template_matches_reference_regions(sample_project):
    metadata = replace(
        sample_project().metadata,
        isbn="9786263211094",
        publisher="台灣角川",
        price="NT$240/HK$80",
        translator="Arieru",
        back_vertical_copy="以四季如夏的無人島為舞台。",
        back_highlight_copy="綾小路同學，你最好趁現在跟人多一點的小組。",
        spine_accent_color="#DF6B32",
    )
    result = apply_template(
        replace(sample_project(), metadata=metadata),
        "modern_vertical_back_with_spine",
    )
    ids = result.elements_by_id
    assert result.background["active_template"] == "modern_vertical_back_with_spine"
    assert ids["back-isbn-code"].transform.y_mm < ids["modern-back-copy-column-1"].transform.y_mm
    assert ids["modern-back-highlight-column-1"].content["color"] == "#DF6B32"
    assert not any(element.id.startswith("modern-back-bottom-decoration") for element in result.elements)
```

- [ ] **Step 5: Add the modern template builder and catalogue entry**

In `templates.py`, add:

```python
TemplateSummary(
    "modern_vertical_back_with_spine",
    "現代直排封底＋可選書脊",
    "可編輯直排內文、醒目文案與三種書脊。",
)
```

Implement `_modern_vertical_back` using:

- Existing ISBN/barcode and publisher information builders for the top `20%` of `back_safe_rect`.
- Black copy target `x=5%`, `y=24%`, `width=61%`, `height=62%`.
- Highlight target `x=69%`, `y=24%`, `width=27%`, `height=62%`.
- No generated elements below `90%` of safe height.
- Each copy column is a vertical `TEXT` element; each separator is a thin `SHAPE`.
- Add layout warnings to `background["warnings"]`.

- [ ] **Step 6: Preserve vertical editing in raster and DOCX**

Update `_render_vertical_text` to treat embedded `\n` as explicit next-column breaks rather than deleting them.

Extend the OOXML signature:

```python
def make_text_box_shape(
    *,
    shape_id: str,
    rect: RectMm,
    rotation_deg: float,
    text: str,
    font_family: str,
    font_size_pt: float,
    color: str,
    align: str,
    line_spacing: float,
    fill: str | None = None,
    stroke: str | None = None,
    behind_text: bool = False,
    z_index: int = 10,
    direction: str = "horizontal",
) -> Any:
    """Build the existing editable VML textbox with explicit text direction."""

def _append_text_with_direction(run, text: str, direction: str) -> None:
    characters = list(text)
    for index, character in enumerate(characters):
        node = OxmlElement("w:t")
        node.text = character
        run.append(node)
        if direction == "vertical" and index < len(characters) - 1:
            run.append(OxmlElement("w:br"))
```

Keep the existing VML shape, textbox, paragraph, font, size, colour, and spacing construction in `make_text_box_shape`; replace its final single `w:t` append with:

```python
_append_text_with_direction(text_run, text, direction)
```

Pass `element.content["direction"]` through `add_text_box`. This keeps each generated column editable in Word and visually vertical without rotating Chinese glyphs.

- [ ] **Step 7: Run back-layout, raster, and DOCX tests**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_vertical_copy_layout.py python-tests/cover/test_modern_back_template.py python-tests/cover/test_render.py python-tests/cover/test_docx_export.py -q
```

Expected: all pass; DOCX XML contains line breaks for vertical columns and no out-of-bounds coordinates.

- [ ] **Step 8: Commit**

```powershell
git add python/src/epub_a4_word/cover/vertical_copy_layout.py python/src/epub_a4_word/cover/templates.py python/src/epub_a4_word/cover/render.py python/src/epub_a4_word/cover/ooxml.py python/src/epub_a4_word/cover/docx_export.py python-tests/cover/test_vertical_copy_layout.py python-tests/cover/test_modern_back_template.py python-tests/cover/test_render.py python-tests/cover/test_docx_export.py
git commit -m "feat: add editable modern vertical back cover"
```

### Task 4: Implement Three Adaptive Spine Styles

**Files:**
- Create: `python/src/epub_a4_word/cover/modern_spine_layout.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Test: `python-tests/cover/test_modern_spine_layout.py`
- Test: `python-tests/cover/test_modern_spine_template.py`

**Interfaces:**
- Produces `build_modern_spine_slots(layout: CoverLayout, style: str, accent: str) -> ModernSpineLayout`.
- `ModernSpineLayout` contains `style`, `tier`, `slots`, and `warnings`.
- Every `SpineSlot.rect` is already inside `layout.spine_rect`; templates must not enlarge it.

- [ ] **Step 1: Write failing style and semantic tests**

```python
@pytest.mark.parametrize(
    ("style", "expected_roles"),
    [
        ("reference_stacked", {"logo", "english_title", "title", "arc", "volume_badge", "author", "code", "publisher"}),
        ("clean_centered", {"logo", "title", "arc", "volume_badge", "author", "publisher"}),
        ("parallel_columns", {"logo", "english_title", "title", "arc", "volume_badge", "author", "code", "publisher"}),
    ],
)
def test_spine_style_roles(style, expected_roles, sample_project):
    project = replace(
        sample_project(manual_spine_width_mm=8.0),
        metadata=replace(sample_project().metadata, spine_style=style),
    )
    layout = build_modern_spine_slots(calculate_layout(project), style, "#DF6B32")
    assert {slot.role for slot in layout.slots} == expected_roles


def test_arc_and_volume_use_distinct_fields(sample_project):
    metadata = replace(
        sample_project().metadata,
        arc_label="二年級篇",
        volume_number="3",
        spine_style="reference_stacked",
    )
    result = apply_template(
        replace(sample_project(manual_spine_width_mm=8.0), metadata=metadata),
        "modern_vertical_back_with_spine",
    )
    assert result.elements_by_id["modern-spine-arc"].content["text"] == "二年級篇"
    assert result.elements_by_id["modern-spine-volume"].content["text"] == "3"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_modern_spine_layout.py python-tests/cover/test_modern_spine_template.py -q
```

Expected: import or missing-element failures.

- [ ] **Step 3: Implement style tables and width tiers**

Create:

```python
ModernSpineTier = Literal["full", "compact", "minimal"]

@dataclass(frozen=True)
class ModernSpineSlot:
    element_id: str
    role: str
    rect: RectMm
    font_size_pt: float
    color: str
    font_weight: int = 400
    direction: str = "vertical"

@dataclass(frozen=True)
class ModernSpineLayout:
    style: str
    tier: ModernSpineTier
    slots: tuple[ModernSpineSlot, ...]
    warnings: tuple[str, ...] = ()
```

Use tier thresholds `>=10 mm`, `>=6 mm`, and `<6 mm`. Define independent slot tables for all three styles. Use the adaptive `spine_safe_rect`; validate every slot with:

```python
def _inside(inner: RectMm, outer: RectMm) -> bool:
    return (
        outer.x_mm <= inner.x_mm
        and inner.right_mm <= outer.right_mm
        and outer.y_mm <= inner.y_mm
        and inner.bottom_mm <= outer.bottom_mm
    )
```

Unknown style values return `reference_stacked` plus a warning.

- [ ] **Step 4: Build stable spine elements**

Add `_modern_spine_elements` to `templates.py`. Map metadata exactly:

```python
values = {
    "title": metadata.title,
    "english_title": metadata.english_title,
    "arc": metadata.arc_label,
    "volume_badge": metadata.volume_number,
    "author": metadata.author,
    "code": metadata.internal_book_code,
    "publisher": metadata.publisher,
}
```

Render `volume_badge` as a circular shape plus centered number. Render Logo with `contain`, centered, and clipped by actual rectangle geometry rather than relying only on masking.

- [ ] **Step 5: Test all width/style combinations and bounds**

Add a cross-product test for widths `4.0`, `6.03`, `8.0`, and `12.0` times all three styles. Assert every element’s `x`, `y`, right, and bottom is within `spine_rect`.

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_modern_spine_layout.py python-tests/cover/test_modern_spine_template.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add python/src/epub_a4_word/cover/modern_spine_layout.py python/src/epub_a4_word/cover/templates.py python-tests/cover/test_modern_spine_layout.py python-tests/cover/test_modern_spine_template.py
git commit -m "feat: add selectable modern spine styles"
```

### Task 5: Generate One Shared Full Trim Frame

**Files:**
- Create: `python/src/epub_a4_word/cover/crop_frame.py`
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word/cover/docx_export.py`
- Modify: `python/src/epub_a4_word/cover/ooxml.py`
- Test: `python-tests/cover/test_crop_frame.py`
- Test: `python-tests/cover/test_render.py`
- Test: `python-tests/cover/test_docx_export.py`
- Test: `python-tests/cover/test_pdf_export.py`

**Interfaces:**
- Produces `CropFrameLine(x1_mm, y1_mm, x2_mm, y2_mm, width_pt=0.35)`.
- Produces `build_crop_frame(project: CoverProject, layout: CoverLayout) -> tuple[CropFrameLine, ...]`.
- Raster preview, PDF, and DOCX call the same function.

- [ ] **Step 1: Write failing geometry and switch tests**

```python
def test_crop_frame_is_exactly_spread_rect(sample_project):
    project = sample_project()
    layout = calculate_layout(project)
    lines = build_crop_frame(project, layout)
    assert {(line.x1_mm, line.y1_mm, line.x2_mm, line.y2_mm) for line in lines} == {
        (layout.spread_rect.x_mm, layout.spread_rect.y_mm, layout.spread_rect.right_mm, layout.spread_rect.y_mm),
        (layout.spread_rect.right_mm, layout.spread_rect.y_mm, layout.spread_rect.right_mm, layout.spread_rect.bottom_mm),
        (layout.spread_rect.right_mm, layout.spread_rect.bottom_mm, layout.spread_rect.x_mm, layout.spread_rect.bottom_mm),
        (layout.spread_rect.x_mm, layout.spread_rect.bottom_mm, layout.spread_rect.x_mm, layout.spread_rect.y_mm),
    }
    assert all(line.width_pt == 0.35 for line in lines)


def test_crop_frame_switch_off_returns_no_lines(sample_project):
    project = replace(
        sample_project(),
        export_settings=replace(sample_project().export_settings, show_crop_marks=False),
    )
    assert build_crop_frame(project, calculate_layout(project)) == ()
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_crop_frame.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement four-line shared geometry**

```python
@dataclass(frozen=True)
class CropFrameLine:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    width_pt: float = 0.35


def build_crop_frame(project, layout):
    if not project.export_settings.show_crop_marks:
        return ()
    rect = layout.spread_rect
    return (
        CropFrameLine(rect.x_mm, rect.y_mm, rect.right_mm, rect.y_mm),
        CropFrameLine(rect.right_mm, rect.y_mm, rect.right_mm, rect.bottom_mm),
        CropFrameLine(rect.right_mm, rect.bottom_mm, rect.x_mm, rect.bottom_mm),
        CropFrameLine(rect.x_mm, rect.bottom_mm, rect.x_mm, rect.y_mm),
    )
```

Validate each coordinate against `layout.bleed_rect`.

- [ ] **Step 4: Draw shared lines in raster preview and PDF**

At the end of `render_spread`, draw lines at exact millimetre-to-pixel coordinates with width `round(0.35 / 72 * dpi)`, minimum one pixel. Since `pdf_export` consumes `render_spread`/`render_print_page`, do not add a separate PDF geometry path.

- [ ] **Step 5: Draw the same lines in DOCX**

Extend `make_line_shape` and `add_line_shape` with `width_pt: float = 0.5`, set VML `strokeweight` from the passed value, and call `build_crop_frame` from `export_docx`. Transform each spread coordinate through the current `PrintPage` intersection before writing it.

- [ ] **Step 6: Verify raster, PDF, and DOCX parity**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests/cover/test_crop_frame.py python-tests/cover/test_render.py python-tests/cover/test_docx_export.py python-tests/cover/test_pdf_export.py -q
```

Expected: all pass; DOCX XML reports `strokeweight="0.35pt"` and all four expected line coordinates.

- [ ] **Step 7: Commit**

```powershell
git add python/src/epub_a4_word/cover/crop_frame.py python/src/epub_a4_word/cover/render.py python/src/epub_a4_word/cover/docx_export.py python/src/epub_a4_word/cover/ooxml.py python-tests/cover/test_crop_frame.py python-tests/cover/test_render.py python-tests/cover/test_docx_export.py python-tests/cover/test_pdf_export.py
git commit -m "feat: add shared full cover crop frame"
```

### Task 6: Add Desktop Editing Controls and Live Refresh

**Files:**
- Modify: `python/src/epub_a4_word_desktop/cover/publisher_metadata_panel.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Test: `desktop/tests/test_publisher_metadata_panel.py`
- Test: `desktop/tests/test_cover_setup_translator.py`
- Test: `desktop/tests/test_template_panel.py`
- Test: `desktop/tests/test_cover_page.py`
- Test: `desktop/tests/test_cover_controller.py`

**Interfaces:**
- Extends `PublisherMetadataValues` with the five fields from Task 1.
- Emits user colour edits as `accent_color_mode="manual"`.
- Provides explicit “重新從封面擷取” action setting mode to `auto`.

- [ ] **Step 1: Write failing desktop widget tests**

```python
def test_modern_cover_fields_are_editable(qtbot):
    panel = PublisherMetadataPanel()
    qtbot.addWidget(panel)
    panel.back_vertical_copy_edit.setPlainText("黑色直排內文")
    panel.back_highlight_copy_edit.setPlainText("醒目文案")
    panel.spine_style_combo.setCurrentIndex(
        panel.spine_style_combo.findData("parallel_columns")
    )
    values = panel.values()
    assert values.back_vertical_copy == "黑色直排內文"
    assert values.back_highlight_copy == "醒目文案"
    assert values.spine_style == "parallel_columns"


def test_manual_colour_edit_switches_mode(qtbot):
    panel = PublisherMetadataPanel()
    qtbot.addWidget(panel)
    panel.spine_accent_color_edit.setText("#336699")
    assert panel.values().accent_color_mode == "manual"


def test_setup_exposes_full_crop_frame_switch(qtbot):
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    panel.show_crop_marks_check.setChecked(False)
    assert panel.values().as_settings()["show_crop_marks"] is False
```

- [ ] **Step 2: Run desktop tests and verify RED**

Run:

```powershell
..\uv\uv.exe run python -m pytest desktop/tests/test_publisher_metadata_panel.py desktop/tests/test_template_panel.py -q
```

Expected: missing widget/property failures.

- [ ] **Step 3: Add multiline fields, style selector, and colour mode**

Use `QPlainTextEdit` for both copy fields and `QComboBox` for style:

```python
self.spine_style_combo.addItem("參考圖分層式", "reference_stacked")
self.spine_style_combo.addItem("極簡置中式", "clean_centered")
self.spine_style_combo.addItem("雙欄現代式", "parallel_columns")
```

Add a checkable “自動從封面取色” control plus “重新從封面擷取” button. Add both copy widgets to the same 300 ms debounced metadata refresh already used by the page.

- [ ] **Step 4: Add the crop-frame switch**

Add `QCheckBox("顯示完整裁切框")` to setup and editor controls. Replace the hard-coded `show_crop_marks=True` setting with the checkbox value. Add a controller method that replaces only:

```python
export_settings=replace(
    project.export_settings,
    show_crop_marks=enabled,
)
```

Then request a fresh preview so the same switch affects preview, DOCX, and PDF.

- [ ] **Step 5: Add new template to setup and editor selectors**

Add `modern_vertical_back_with_spine` to both template combo boxes. Treat both publisher template IDs as publisher-metadata templates so the shared panel remains visible.

- [ ] **Step 6: Preserve values through controller refresh and reset**

Update controller metadata replacement and `refresh_template_metadata` calls to carry all new fields. Style changes intentionally call template reset for spine-managed elements only; text changes preserve current transforms where IDs already exist.

- [ ] **Step 7: Run focused desktop tests**

Run:

```powershell
..\uv\uv.exe run python -m pytest desktop/tests/test_publisher_metadata_panel.py desktop/tests/test_cover_setup_translator.py desktop/tests/test_template_panel.py desktop/tests/test_cover_page.py desktop/tests/test_cover_controller.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add python/src/epub_a4_word_desktop/cover/publisher_metadata_panel.py python/src/epub_a4_word_desktop/cover/setup_panel.py python/src/epub_a4_word_desktop/pages/cover_page.py python/src/epub_a4_word_desktop/cover/controller.py desktop/tests/test_publisher_metadata_panel.py desktop/tests/test_cover_setup_translator.py desktop/tests/test_template_panel.py desktop/tests/test_cover_page.py desktop/tests/test_cover_controller.py
git commit -m "feat: add desktop modern cover controls"
```

### Task 7: Add Android Editing Controls and Shared Preview State

**Files:**
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverUiState.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverSetupScreen.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverCapabilities.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverEditorScreen.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/ExportCoverDialog.kt`
- Test: `app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewModelTest.kt`
- Test: `app/src/test/java/tw/daniel/epubword/cover/ui/AndroidCoverCapabilitiesRegressionTest.kt`
- Test: `app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverSetupScreenTest.kt`
- Test: `app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverEditorScreenTest.kt`

**Interfaces:**
- `CoverUiState` mirrors all Task 1 metadata.
- `CoverViewModel` sends the exact JSON keys consumed by Python.
- Android preview remains the Python-rendered bitmap; it does not duplicate back-cover or crop-frame geometry.

- [ ] **Step 1: Write failing ViewModel and capability tests**

```kotlin
@Test
fun createProjectSendsModernCoverFields() = runTest {
    viewModel.setBackVerticalCopy("黑色直排內文")
    viewModel.setBackHighlightCopy("醒目文案")
    viewModel.setSpineStyle("parallel_columns")
    viewModel.setMetadataSpineAccentColor("#336699")
    viewModel.createProject()
    val settings = gateway.lastNewProjectSettings!!
    assertEquals("黑色直排內文", settings.getString("back_vertical_copy"))
    assertEquals("醒目文案", settings.getString("back_highlight_copy"))
    assertEquals("parallel_columns", settings.getString("spine_style"))
    assertEquals("manual", settings.getString("accent_color_mode"))
}

@Test
fun cropFrameSwitchUpdatesSharedProjectSetting() = runTest {
    viewModel.setShowCropMarks(false)
    assertFalse(viewModel.uiState.value.project!!.exportSettings.showCropMarks)
    assertTrue(gateway.previewRequests.isNotEmpty())
}
```

- [ ] **Step 2: Run Android unit tests and verify RED**

Run:

```powershell
gradle --no-daemon :app:testDebugUnitTest --tests "tw.daniel.epubword.cover.ui.CoverViewModelTest"
```

Expected: missing setter/state failures.

- [ ] **Step 3: Extend Android state and ViewModel**

Add state fields:

```kotlin
val metadataBackVerticalCopy: String = "",
val metadataBackHighlightCopy: String = "",
val metadataSpineStyle: String = "reference_stacked",
val metadataAccentColorMode: String = "auto",
val metadataExtractedAccentColor: String = "",
```

Add setters, parse fields from opened project JSON, and write exact snake-case keys during project creation and metadata refresh.

- [ ] **Step 4: Add Compose controls**

In `PublisherMetadataCard`, add two multiline `OutlinedTextField`s with `minLines = 4`, three `FilterChip`s for style, an automatic-colour checkbox, a colour field, and a “重新從封面擷取” button. Show the metadata card for both existing and modern publisher templates.

- [ ] **Step 5: Add one crop-frame switch**

Add `showCropMarks` to setup/editor state and a `Checkbox` labelled `顯示完整裁切框` in the appearance/export controls. `setShowCropMarks` replaces only `project.exportSettings.showCropMarks`, serializes through the existing project JSON path, and immediately requests a new Python preview.

- [ ] **Step 6: Keep crop-frame geometry in Python**

Do not add Kotlin crop coordinates. Confirm Android preview requests a fresh Python-rendered preview after `showCropMarks`, copy, style, or accent changes. Add a regression assertion that Android does not define `buildCropFrame` or hard-coded spread coordinates.

- [ ] **Step 7: Run Android unit and instrumentation compile checks**

Run:

```powershell
gradle --no-daemon :app:testDebugUnitTest :app:assembleDebug
```

Expected: build succeeds and unit tests pass. Instrumentation test sources compile as part of the debug Android test configuration.

- [ ] **Step 8: Commit**

```powershell
git add app/src/main/java/tw/daniel/epubword/cover/ui/CoverUiState.kt app/src/main/java/tw/daniel/epubword/cover/ui/CoverSetupScreen.kt app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt app/src/main/java/tw/daniel/epubword/cover/ui/CoverCapabilities.kt app/src/main/java/tw/daniel/epubword/cover/ui/CoverEditorScreen.kt app/src/main/java/tw/daniel/epubword/cover/ui/ExportCoverDialog.kt app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewModelTest.kt app/src/test/java/tw/daniel/epubword/cover/ui/AndroidCoverCapabilitiesRegressionTest.kt app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverSetupScreenTest.kt app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverEditorScreenTest.kt
git commit -m "feat: add Android modern cover controls"
```

### Task 8: Add Cross-Platform Regression Fixtures and Prepare v0.7.0

**Files:**
- Create: `python-tests/cover/test_modern_cover_reference.py`
- Modify: `python-tests/cover/test_golden_exports.py`
- Modify: `python-tests/test_android_bridge.py`
- Modify: `pyproject.toml`
- Modify: `python/src/epub_a4_word/__init__.py`
- Modify: `app/build.gradle.kts`
- Verify: `.github/workflows/release.yml`

**Interfaces:**
- Locks the approved reference geometry and no-bottom-decoration rule.
- Publishes version `0.7.0` consistently across Python and Android.

- [ ] **Step 1: Add an exact reference-project regression**

Build a project with:

```python
CoverMetadata(
    title="歡迎來到實力至上主義的教室",
    author="衣笠彰梧",
    isbn="9786263211094",
    publisher="台灣角川",
    price="NT$240/HK$80",
    translator="Arieru",
    english_title="Welcome to the Classroom of the Elite",
    arc_label="二年級篇",
    volume_number="3",
    internal_book_code="CL0308-17",
    back_vertical_copy="以四季如夏的無人島為舞台，全年級互相競賽。",
    back_highlight_copy="綾小路同學，你最好趁現在跟人多一點的小組。",
    spine_style="reference_stacked",
)
```

Assert:

- Top barcode and publisher stack occupy the top region.
- Black columns and highlight columns occupy their approved middle regions.
- No generated bottom decoration IDs exist.
- Every back element is inside `back_safe_rect`.
- Every spine element is inside `spine_rect`.
- The crop frame equals `spread_rect`.

- [ ] **Step 2: Add rendered golden geometry checks**

Render at 300 DPI and use fixed pixel probes for:

- white bottom blank area,
- black body-copy area,
- extracted accent highlight area,
- four crop-frame edges,
- theme-colour volume badge.

Do not compare the reference photograph or embed it in the repository.

- [ ] **Step 3: Bump versions**

Set:

```toml
version = "0.7.0"
```

Set Python `__version__ = "0.7.0"`.

Set Android:

```kotlin
versionCode = 8
versionName = "0.7.0"
```

Update bridge/version tests to expect `0.7.0`.

- [ ] **Step 4: Run full Python and desktop suites**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests -q
..\uv\uv.exe run python -m pytest desktop/tests -q
```

Expected: all tests pass; only documented optional skips remain.

- [ ] **Step 5: Build and verify Android**

Run:

```powershell
gradle --no-daemon :app:testDebugUnitTest :app:assembleDebug
```

Expected: `BUILD SUCCESSFUL` and `app/build/outputs/apk/debug/app-debug.apk` exists.

- [ ] **Step 6: Build and smoke-test Windows Portable**

Run:

```powershell
..\uv\uv.exe run python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec
New-Item -ItemType File -Path 'dist/EPUB2A4-Windows-Portable-x64/portable.flag' -Force | Out-Null
..\uv\uv.exe run python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64
& 'dist/EPUB2A4-Windows-Portable-x64/EPUB2A4.exe' --portable-smoke-test
```

Expected: verifier exits `0` and smoke test exits `0`.

- [ ] **Step 7: Confirm release workflow contract**

Inspect `.github/workflows/release.yml` and verify it still:

- triggers on `v*` tags,
- builds Android and Windows,
- creates `EPUB2A4-Android.apk`,
- creates `EPUB2A4-Windows-Portable-x64.zip`,
- generates `SHA256SUMS.txt`.

No workflow edit is needed when all five assertions hold.

- [ ] **Step 8: Commit**

```powershell
git add python-tests/cover/test_modern_cover_reference.py python-tests/cover/test_golden_exports.py python-tests/test_android_bridge.py pyproject.toml python/src/epub_a4_word/__init__.py app/build.gradle.kts
git commit -m "chore: prepare v0.7.0"
```

### Task 9: Review, Integrate, and Publish

**Files:**
- Review: all files changed by Tasks 1–8

**Interfaces:**
- Produces a green PR against `main`.
- Produces tag and Release `v0.7.0`.

- [ ] **Step 1: Run final diff hygiene checks**

Run:

```powershell
git diff --check origin/main...HEAD
git status --short
git log --oneline origin/main..HEAD
```

Expected: no whitespace errors; `.superpowers/` and `uv.lock` remain untracked and are not committed.

- [ ] **Step 2: Request code review**

Use `superpowers:requesting-code-review`. Address any correctness finding before publishing.

- [ ] **Step 3: Re-run full verification on the reviewed commit**

Run:

```powershell
..\uv\uv.exe run python -m pytest python-tests -q
..\uv\uv.exe run python -m pytest desktop/tests -q
gradle --no-daemon :app:testDebugUnitTest :app:assembleDebug
```

Expected: all commands pass.

- [ ] **Step 4: Push and open a ready PR**

```powershell
git push -u origin feat/modern-cover-layout-v070
```

Create a ready PR titled `新增現代直排封底、三種書脊與裁切框（v0.7.0）` against `main`. Include the root design decisions, exact tests, Android build, and Windows smoke test.

- [ ] **Step 5: Wait for all PR workflows**

Require success from:

- `Android debug APK`
- `Desktop PySide6 tests`
- `Windows portable EXE`

Do not merge while any required run is queued, in progress, cancelled, or failed.

- [ ] **Step 6: Squash merge with expected head SHA**

Squash PR into `main` using the reviewed branch head SHA to reject stale merges.

- [ ] **Step 7: Tag the merge commit**

```powershell
git fetch origin main --tags
$mergeSha = git rev-parse origin/main
git show --no-patch --oneline $mergeSha
git tag -a v0.7.0 $mergeSha -m "Release v0.7.0"
git push origin v0.7.0
```

Before tagging, compare `$mergeSha` to the exact SHA returned by GitHub’s successful merge response and stop if they differ.

- [ ] **Step 8: Verify the Release and download assets**

Wait for the tag-triggered `Release` workflow to complete successfully. Confirm the Release is neither draft nor prerelease and these URLs return HTTP `200`:

```text
https://github.com/eightkingdomsalliedforces-hash/epub2a4/releases/download/v0.7.0/EPUB2A4-Android.apk
https://github.com/eightkingdomsalliedforces-hash/epub2a4/releases/download/v0.7.0/EPUB2A4-Windows-Portable-x64.zip
https://github.com/eightkingdomsalliedforces-hash/epub2a4/releases/download/v0.7.0/SHA256SUMS.txt
```

Expected: all three assets exist and return `200`.
