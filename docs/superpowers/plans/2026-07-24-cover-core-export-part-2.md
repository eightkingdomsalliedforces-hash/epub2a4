# Shared Cover Core and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canonical Python cover engine used by Android and desktop for metadata inspection, project JSON, spine and A4 geometry, local templates, preview rendering, PDF export, and editable DOCX export.

**Architecture:** Move the existing Python conversion package to one repository-level source tree and point Chaquopy at it rather than maintaining an Android-only copy. Add a focused `epub_a4_word.cover` package whose public service API accepts paths, primitive values, and UTF-8 JSON so Kotlin and PySide6 receive identical results.

**Tech Stack:** Python 3.13, dataclasses, Pillow 11.0.0, python-docx 1.1.2, lxml 5.3.0, pypdf 6.14.2, pytest; Chaquopy source sets; OOXML DrawingML/VML.

## Global Constraints

- Android remains API 24+ and arm64-v8a.
- The canonical package is `python/src/epub_a4_word`; no second committed copy may remain under `app/src/main/python/epub_a4_word`.
- `CoverProject.schema_version` is `1`.
- All dimensions and positions are stored as decimal millimetres.
- Cover order is `back | spine | front`.
- Supported trim sizes: A5 `148 × 210 mm`, A6 `105 × 148 mm`, 4×6 inch `101.6 × 152.4 mm`.
- Default bleed is `3 mm`, valid range `0..10 mm`.
- Automatic spine width is `ceil(page_count / 2) × paper_caliper_mm`.
- Default overlap is exactly `5 mm`.
- Never scale a finished cover to fit A4.
- PDF is the print reference and defaults to `300 DPI`; Android may explicitly request `200 DPI`.
- DOCX page size is exact A4 and principal text/image elements remain individually editable.
- Existing EPUB and DOCX conversion tests must remain green.

---

## Part 2: Tasks 4–7

### Task 4: Calculate spine, spread, safe zones, and A4 print tiles

**Files:**
- Create: `python/src/epub_a4_word/cover/geometry.py`
- Create: `python/src/epub_a4_word/cover/print_plan.py`
- Create: `python-tests/cover/test_geometry.py`
- Create: `python-tests/cover/test_print_plan.py`

**Interfaces:**
- Produces: `calculate_layout(project: CoverProject) -> CoverLayout`.
- Produces: `build_print_plan(layout: CoverLayout) -> PrintPlan`.
- `CoverLayout` exposes `spine_width_mm`, `spread_rect`, `back_rect`, `spine_rect`, `front_rect`, `bleed_rect`, and region safe rectangles.
- `PrintPlan.mode` is `single` or `split`; each `PrintPage` is exact A4 portrait or landscape.

- [ ] **Step 1: Write failing spine and panel-coordinate tests**

```python
def test_spine_uses_sheet_count_and_caliper(sample_project):
    layout = calculate_layout(sample_project(page_count=161, paper_caliper_mm=0.10))
    assert layout.sheet_count == 81
    assert layout.spine_width_mm == pytest.approx(8.1)


def test_manual_spine_override_wins(sample_project):
    layout = calculate_layout(sample_project(manual_spine_width_mm=9.4))
    assert layout.spine_width_mm == pytest.approx(9.4)


def test_cover_order_is_back_spine_front(sample_project):
    layout = calculate_layout(sample_project(trim=(105.0, 148.0), bleed_mm=3.0))
    assert layout.back_rect.x_mm == pytest.approx(3.0)
    assert layout.spine_rect.x_mm == pytest.approx(108.0)
    assert layout.front_rect.x_mm == pytest.approx(108.0 + layout.spine_width_mm)
```

- [ ] **Step 2: Write failing A4 single/split tests**

```python
def test_a6_spread_fits_one_landscape_a4(sample_project):
    plan = build_print_plan(calculate_layout(sample_project(trim=(105.0, 148.0))))
    assert plan.mode == "single"
    assert len(plan.pages) == 1
    assert plan.pages[0].orientation == "landscape"
    assert plan.pages[0].paper_size_mm == (297.0, 210.0)


def test_a5_spread_splits_without_scaling(sample_project):
    plan = build_print_plan(calculate_layout(sample_project(trim=(148.0, 210.0))))
    assert plan.mode == "split"
    assert [page.name for page in plan.pages] == ["back", "spine", "front"]
    assert all(page.scale == 1.0 for page in plan.pages)
    assert plan.pages[0].source_rect.width_mm == pytest.approx(148.0 + 3.0 + 5.0)
    assert plan.pages[1].left_overlap_mm == pytest.approx(5.0)
    assert plan.pages[1].right_overlap_mm == pytest.approx(5.0)
```

- [ ] **Step 3: Implement geometry dataclasses and calculations**

Use:

```python
@dataclass(frozen=True)
class RectMm:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class CoverLayout:
    sheet_count: int
    spine_width_mm: float
    spread_rect: RectMm
    bleed_rect: RectMm
    back_rect: RectMm
    spine_rect: RectMm
    front_rect: RectMm
    back_safe_rect: RectMm
    spine_safe_rect: RectMm
    front_safe_rect: RectMm
```

Core calculation:

```python
sheet_count = math.ceil(project.page_count / 2)
auto_spine = sheet_count * project.paper_caliper_mm
spine = project.manual_spine_width_mm or auto_spine
trim_w = project.trim_size.width_mm
trim_h = project.trim_size.height_mm
bleed = project.bleed_mm
spread_w = trim_w * 2 + spine
```

Set panel Y to `bleed`, panel height to `trim_h`, and the outer canvas to `spread_w + 2*bleed` by `trim_h + 2*bleed`. Use a default safe inset of `5 mm` inside trim edges and `3 mm` away from each spine fold.

- [ ] **Step 4: Implement exact A4 tiling and marks**

Use:

```python
A4_PORTRAIT = (210.0, 297.0)
A4_LANDSCAPE = (297.0, 210.0)

@dataclass(frozen=True)
class PrintPage:
    name: str
    orientation: str
    paper_size_mm: tuple[float, float]
    source_rect: RectMm
    destination_rect: RectMm
    scale: float
    left_overlap_mm: float = 0.0
    right_overlap_mm: float = 0.0
    marks: tuple[PrintMark, ...] = ()
```

Single-page rule:

```python
if layout.bleed_rect.width_mm <= 297.0 and layout.bleed_rect.height_mm <= 210.0:
    return centered_landscape_page(layout.bleed_rect)
```

Split-page source rectangles:

- back: outer bleed through `5 mm` into spine.
- spine: spine plus `5 mm` from both adjacent panels.
- front: `5 mm` into spine through outer bleed.

Choose portrait or landscape independently for each tile; select the orientation which fits at scale `1.0` and leaves the larger minimum margin. Raise `CoverLayoutError` if a tile cannot fit A4 at 1:1. Add crop marks at every trim corner and assembly labels outside the source rectangle.

- [ ] **Step 5: Run geometry tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest \
  python-tests/cover/test_geometry.py python-tests/cover/test_print_plan.py -q
git add python/src/epub_a4_word/cover/geometry.py \
  python/src/epub_a4_word/cover/print_plan.py python-tests/cover
git commit -m "feat: calculate full-cover and A4 tile geometry"
```

Expected: all tests PASS and no coordinate differs by more than `1e-6 mm` in pure calculations.

---

### Task 5: Apply deterministic local cover templates

**Files:**
- Create: `python/src/epub_a4_word/cover/templates.py`
- Create: `python-tests/cover/test_templates.py`

**Interfaces:**
- Produces: `list_templates() -> tuple[TemplateSummary, ...]`.
- Produces: `apply_template(project: CoverProject, template_id: str) -> CoverProject`.
- Template IDs: `minimal_text`, `front_image_plain_back`, `full_spread`, `top_bottom_blocks`.

- [ ] **Step 1: Write failing template tests**

```python
@pytest.mark.parametrize("template_id", [
    "minimal_text",
    "front_image_plain_back",
    "full_spread",
    "top_bottom_blocks",
])
def test_template_creates_unique_elements(sample_project, template_id):
    result = apply_template(sample_project, template_id)
    assert len({element.id for element in result.elements}) == len(result.elements)
    assert any(e.id == "front-title" for e in result.elements)
    assert any(e.id == "spine-title" for e in result.elements)
    assert any(e.id == "back-description" for e in result.elements)


def test_full_spread_template_sets_image_mode(sample_project):
    result = apply_template(sample_project, "full_spread")
    assert result.image_mode is ImageMode.FULL_SPREAD
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_templates.py -q
```

Expected: collection ERROR because `cover.templates` does not exist.

- [ ] **Step 3: Implement reusable element constructors**

Define helpers whose positions come only from `calculate_layout(project)`:

```python
def text_element(
    element_id: str,
    region: Region,
    rect: RectMm,
    text: str,
    font_size_pt: float,
    align: str = "center",
    rotation_deg: float = 0.0,
) -> CoverElement:
    return CoverElement(
        id=element_id,
        kind=ElementKind.TEXT,
        region=region,
        transform=ElementTransform(
            rect.x_mm, rect.y_mm, rect.width_mm, rect.height_mm, rotation_deg
        ),
        content={
            "text": text,
            "font_family": "sans-serif",
            "font_size_pt": font_size_pt,
            "font_weight": 400,
            "color": "#111111",
            "align": align,
            "line_spacing": 1.15,
            "direction": "horizontal",
        },
    )
```

Every template must produce front title/author, spine title/author, back description, publisher, and an optional ISBN placeholder. `apply_template` replaces only elements whose IDs begin with `template-` or match the standard template IDs; user-added elements remain intact.

- [ ] **Step 4: Implement the four templates and overflow warnings**

Template layout must use safe rectangles. If the spine is narrower than `4 mm`, omit spine author and set spine title font to `6 pt`; if narrower than `2 mm`, omit all spine text and append a project warning in `background["warnings"]`.

```python
def _spine_elements(project: CoverProject, layout: CoverLayout) -> tuple[CoverElement, ...]:
    width = layout.spine.width_mm
    warnings = list(project.background.get("warnings", []))
    if width < 2.0:
        warnings.append("書脊小於 2 mm，已省略書脊文字。")
        project.background["warnings"] = warnings
        return ()

    elements = [
        text_element(
            "spine-title",
            Region.SPINE,
            layout.spine_safe,
            project.metadata.title,
            6.0 if width < 4.0 else 8.0,
            rotation_deg=90.0,
        )
    ]
    if width >= 4.0 and project.metadata.author:
        elements.append(
            text_element(
                "spine-author",
                Region.SPINE,
                layout.spine_author_safe,
                project.metadata.author,
                6.0,
                rotation_deg=90.0,
            )
        )
    return tuple(elements)


def apply_template(project: CoverProject, template_id: str) -> CoverProject:
    builders = {
        "minimal_text": _minimal_text,
        "front_image_plain_back": _front_image_plain_back,
        "full_spread": _full_spread,
        "top_bottom_blocks": _top_bottom_blocks,
    }
    try:
        builder = builders[template_id]
    except KeyError as exc:
        raise ValueError(f"未知封面模板：{template_id}") from exc
    retained = tuple(e for e in project.elements if e.id not in STANDARD_TEMPLATE_IDS)
    generated = builder(project, calculate_layout(project))
    return replace(project, elements=retained + generated)
```

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_templates.py -q
git add python/src/epub_a4_word/cover/templates.py python-tests/cover/test_templates.py
git commit -m "feat: add deterministic local cover templates"
```

Expected: all tests PASS.

---

### Task 6: Render project previews and print tiles with Pillow

**Files:**
- Create: `python/src/epub_a4_word/cover/render.py`
- Create: `python/src/epub_a4_word/cover/fonts.py`
- Create: `python-tests/cover/test_render.py`

**Interfaces:**
- Produces: `render_spread(project, dpi) -> PIL.Image.Image`.
- Produces: `render_preview(project, output_path, max_px=1600) -> RenderResult`.
- Produces: `render_print_page(project, page, dpi) -> PIL.Image.Image`.
- Rendering order is ascending `z_index`, then stable element order.

- [ ] **Step 1: Write failing pixel-size and clipping tests**

```python
def test_spread_pixel_size_matches_mm(sample_project):
    image = render_spread(sample_project, dpi=300)
    layout = calculate_layout(sample_project)
    assert image.width == round(layout.bleed_rect.width_mm / 25.4 * 300)
    assert image.height == round(layout.bleed_rect.height_mm / 25.4 * 300)


def test_front_only_image_does_not_paint_back(sample_project_with_red_image):
    image = render_spread(sample_project_with_red_image, dpi=100)
    layout = calculate_layout(sample_project_with_red_image)
    back_x = mm_to_px(layout.back_rect.x_mm + 5, 100)
    front_x = mm_to_px(layout.front_rect.x_mm + 5, 100)
    y = mm_to_px(layout.front_rect.y_mm + 5, 100)
    assert image.getpixel((back_x, y)) != image.getpixel((front_x, y))


def test_preview_caps_longest_edge(sample_project, tmp_path):
    result = render_preview(sample_project, tmp_path / "preview.png", max_px=900)
    assert max(result.width_px, result.height_px) == 900
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_render.py -q
```

Expected: collection ERROR because `cover.render` does not exist.

- [ ] **Step 3: Implement millimetre conversion and image transforms**

Use:

```python
def mm_to_px(value_mm: float, dpi: int) -> int:
    return max(0, round(value_mm / 25.4 * dpi))


def _fit_image(source: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    if fit == "contain":
        result = ImageOps.contain(source, (width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(result, ((width - result.width) // 2, (height - result.height) // 2))
        return canvas
    return ImageOps.fit(source, (width, height), Image.Resampling.LANCZOS)
```

Apply crop, rotation, flip, opacity, blur, brightness, dark overlay, and gradient values from element `content`. Clip `FRONT_ONLY` images to `layout.front_rect`; clip `FULL_SPREAD` images to `layout.bleed_rect`.

- [ ] **Step 4: Implement text, shapes, guides, and deterministic font fallback**

`fonts.py` must expose:

```python
def resolve_font(font_family: str, font_path: str | None, size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [font_path, os.environ.get("EPUB2A4_DEFAULT_FONT")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return ImageFont.truetype(candidate, size_px)
    return ImageFont.load_default(size=max(8, size_px))
```

Text rendering must support horizontal and rotated spine text, alignment, line spacing, box clipping, and an overflow flag. Guides are excluded from final output unless `content["printable"] is True`.

- [ ] **Step 5: Implement A4 page rendering**

Create an exact A4 canvas in the page orientation, paste the corresponding 1:1 crop from the spread at `destination_rect`, and draw crop/assembly marks outside trim content. No resampling is allowed when source and destination DPI match.

```python
def render_print_page(
    project: CoverProject,
    page: PrintPage,
    dpi: int,
) -> Image.Image:
    spread = render_spread(project, dpi)
    page_w_mm, page_h_mm = page.page_size_mm
    canvas = Image.new(
        "RGB",
        (mm_to_px(page_w_mm, dpi), mm_to_px(page_h_mm, dpi)),
        "white",
    )
    source_box = tuple(mm_to_px(value, dpi) for value in page.source_rect.to_xyxy())
    destination = (
        mm_to_px(page.destination_rect.x_mm, dpi),
        mm_to_px(page.destination_rect.y_mm, dpi),
    )
    crop = spread.crop(source_box)
    expected_size = (
        mm_to_px(page.destination_rect.width_mm, dpi),
        mm_to_px(page.destination_rect.height_mm, dpi),
    )
    if crop.size != expected_size:
        raise ValueError(f"列印裁片尺寸不一致：{crop.size} != {expected_size}")
    canvas.paste(crop, destination)
    draw = ImageDraw.Draw(canvas)
    for mark in page.marks:
        _draw_print_mark(draw, mark, dpi)
    return canvas
```

- [ ] **Step 6: Run render tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_render.py -q
git add python/src/epub_a4_word/cover/render.py \
  python/src/epub_a4_word/cover/fonts.py python-tests/cover/test_render.py
git commit -m "feat: render cover previews and print pages"
```

Expected: all tests PASS.

---

### Task 7: Export exact A4 PDF files

**Files:**
- Create: `python/src/epub_a4_word/cover/pdf_export.py`
- Create: `python-tests/cover/test_pdf_export.py`

**Interfaces:**
- Produces: `export_pdf(project: CoverProject, output_path: Path, dpi: int = 300) -> ExportResult`.
- `ExportResult` fields: `path`, `page_count`, `mode`, `dpi`, `warnings`.

- [ ] **Step 1: Write failing PDF structure tests**

```python
from pypdf import PdfReader


def points_to_mm(points: float) -> float:
    return points / 72.0 * 25.4


def test_single_pdf_is_one_landscape_a4_page(a6_project, tmp_path):
    result = export_pdf(a6_project, tmp_path / "cover.pdf", dpi=300)
    reader = PdfReader(result.path)
    page = reader.pages[0]
    assert len(reader.pages) == 1
    assert points_to_mm(float(page.mediabox.width)) == pytest.approx(297.0, abs=0.05)
    assert points_to_mm(float(page.mediabox.height)) == pytest.approx(210.0, abs=0.05)


def test_split_pdf_has_back_spine_front_order(a5_project, tmp_path):
    result = export_pdf(a5_project, tmp_path / "cover.pdf", dpi=300)
    assert result.mode == "split"
    assert result.page_count == 3
    assert [m.get("/Title") for m in PdfReader(result.path).pages] == [None, None, None]
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_pdf_export.py -q
```

Expected: collection ERROR because `cover.pdf_export` does not exist.

- [ ] **Step 3: Implement multi-page Pillow PDF export**

```python
def export_pdf(project: CoverProject, output_path: Path | str, dpi: int = 300) -> ExportResult:
    if dpi not in {200, 300}:
        raise ValueError("PDF DPI 只支援 200 或 300。")
    layout = calculate_layout(project)
    plan = build_print_plan(layout)
    pages = [render_print_page(project, page, dpi).convert("RGB") for page in plan.pages]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(
        output,
        "PDF",
        resolution=float(dpi),
        save_all=True,
        append_images=pages[1:],
        title=project.metadata.title,
        author=project.metadata.author,
    )
    return ExportResult(output, len(pages), plan.mode, dpi, ())
```

After save, reopen with `PdfReader` and verify each MediaBox matches the planned A4 orientation within `0.05 mm`; delete the output and raise `CoverExportError` if validation fails.

- [ ] **Step 4: Run tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_pdf_export.py -q
git add python/src/epub_a4_word/cover/pdf_export.py python-tests/cover/test_pdf_export.py
git commit -m "feat: export exact A4 cover PDF"
```

Expected: all tests PASS.

---
