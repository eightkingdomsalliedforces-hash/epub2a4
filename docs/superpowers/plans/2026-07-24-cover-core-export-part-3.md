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

## Part 3: Tasks 8–10

### Task 8: Export editable A4 DOCX with anchored objects

**Files:**
- Create: `python/src/epub_a4_word/cover/ooxml.py`
- Create: `python/src/epub_a4_word/cover/docx_export.py`
- Create: `python-tests/cover/test_docx_export.py`

**Interfaces:**
- Produces: `export_docx(project: CoverProject, output_path: Path) -> ExportResult`.
- Produces internal helpers: `add_anchored_picture`, `add_text_box`, `add_line_shape`.
- Every `PrintPage` becomes one Word section/page with exact A4 orientation and zero margins.

- [ ] **Step 1: Write failing OOXML tests**

```python
from zipfile import ZipFile
from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
}


def test_docx_has_editable_text_and_picture_objects(a6_project, tmp_path):
    path = export_docx(a6_project, tmp_path / "cover.docx").path
    with ZipFile(path) as package:
        document = etree.fromstring(package.read("word/document.xml"))
        assert document.xpath("count(.//wp:anchor)", namespaces=NS) >= 1
        assert document.xpath("count(.//w:txbxContent)", namespaces=NS) >= 3
        assert "範例書" in "".join(document.xpath(".//w:t/text()", namespaces=NS))


def test_split_docx_has_three_sections(a5_project, tmp_path):
    path = export_docx(a5_project, tmp_path / "cover.docx").path
    with ZipFile(path) as package:
        document = etree.fromstring(package.read("word/document.xml"))
        assert document.xpath("count(.//w:sectPr)", namespaces=NS) == 3
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_docx_export.py -q
```

Expected: collection ERROR because `cover.docx_export` does not exist.

- [ ] **Step 3: Implement page sections and EMU conversion**

Use exact conversions:

```python
EMU_PER_MM = 36000
TWIPS_PER_MM = 1440 / 25.4


def mm_to_emu(mm: float) -> int:
    return round(mm * EMU_PER_MM)


def mm_to_twips(mm: float) -> int:
    return round(mm * TWIPS_PER_MM)
```

For each page:

- create a section break after the prior page;
- set `w:pgSz` to A4 portrait or landscape;
- set all margins, header distance, footer distance, and gutter to `0`;
- add one empty anchor paragraph which holds all absolutely positioned objects;
- add a final page break only between sections, never after the last section.

- [ ] **Step 4: Implement editable pictures and text boxes**

`add_anchored_picture` must create `wp:anchor` with page-relative `positionH` and `positionV`, `wp:extent`, `wp:wrapNone`, and a unique drawing ID. Use `python-docx` relationships for image parts and low-level XML for placement.

`add_text_box` must create a VML `v:shape` containing `v:textbox` and `w:txbxContent`, with explicit `margin-left/top:0`, width/height in points, absolute page position, rotation, fill, stroke, font, paragraph alignment, and line spacing. Text remains a real `w:t` node.

When an image spans multiple split pages, create one editable image object per page using the same original file and DrawingML `a:srcRect` crop percentages. Do not rasterize text into the page background.

```python
def add_anchored_picture(
    paragraph,
    image_path: Path,
    rect: RectMm,
    crop: CropPercent,
    drawing_id: int,
) -> None:
    part = paragraph.part
    relationship_id, image = part.get_or_add_image(str(image_path))
    anchor = make_anchor(
        relationship_id=relationship_id,
        drawing_id=drawing_id,
        x_emu=mm_to_emu(rect.x_mm),
        y_emu=mm_to_emu(rect.y_mm),
        width_emu=mm_to_emu(rect.width_mm),
        height_emu=mm_to_emu(rect.height_mm),
        crop_left=crop.left,
        crop_top=crop.top,
        crop_right=crop.right,
        crop_bottom=crop.bottom,
    )
    paragraph._p.append(anchor)


def add_text_box(paragraph, element: CoverElement, rect: RectMm) -> None:
    shape = make_text_box_shape(
        shape_id=f"textbox-{element.id}",
        x_pt=rect.x_mm * 72.0 / 25.4,
        y_pt=rect.y_mm * 72.0 / 25.4,
        width_pt=rect.width_mm * 72.0 / 25.4,
        height_pt=rect.height_mm * 72.0 / 25.4,
        rotation_deg=element.transform.rotation_deg,
        text=str(element.content["text"]),
        font_family=str(element.content["font_family"]),
        font_size_pt=float(element.content["font_size_pt"]),
        color=str(element.content["color"]),
        align=str(element.content["align"]),
        line_spacing=float(element.content["line_spacing"]),
    )
    paragraph._p.append(shape)
```

- [ ] **Step 5: Add crop lines and assembly labels as editable objects**

Use VML line shapes for crop and assembly marks and text boxes for `封底`, `書脊`, `正面`, and assembly direction labels. Set these objects behind principal text but above the page background.

```python
def add_print_marks(paragraph, page: PrintPage) -> None:
    for index, mark in enumerate(page.marks, start=1):
        if mark.kind == "line":
            paragraph._p.append(
                make_line_shape(
                    shape_id=f"mark-{page.name}-{index}",
                    x1_pt=mark.x1_mm * 72.0 / 25.4,
                    y1_pt=mark.y1_mm * 72.0 / 25.4,
                    x2_pt=mark.x2_mm * 72.0 / 25.4,
                    y2_pt=mark.y2_mm * 72.0 / 25.4,
                    behind_text=True,
                )
            )
        elif mark.kind == "label":
            paragraph._p.append(
                make_label_shape(
                    shape_id=f"label-{page.name}-{index}",
                    text=mark.text,
                    x_pt=mark.x_mm * 72.0 / 25.4,
                    y_pt=mark.y_mm * 72.0 / 25.4,
                    width_pt=mark.width_mm * 72.0 / 25.4,
                    height_pt=mark.height_mm * 72.0 / 25.4,
                    behind_text=True,
                )
            )
```

- [ ] **Step 6: Validate the generated package and commit**

After saving, reopen with `python-docx` and `ZipFile`; verify required parts and relationships exist. Run:

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_docx_export.py -q
git add python/src/epub_a4_word/cover/ooxml.py \
  python/src/epub_a4_word/cover/docx_export.py python-tests/cover/test_docx_export.py
git commit -m "feat: export editable A4 cover DOCX"
```

Expected: all tests PASS.

---

### Task 9: Expose one service API and Android JSON bridge

**Files:**
- Create: `python/src/epub_a4_word/cover/service.py`
- Modify: `python/src/epub_a4_word/cover/__init__.py`
- Modify: `app/src/main/python/android_bridge.py`
- Create: `python-tests/cover/test_service.py`
- Modify: `python-tests/test_android_bridge.py`

**Interfaces:**
- Produces the frozen functions from the roadmap:
  - `inspect_source(source_path: str) -> dict`
  - `new_project(source_path: str, settings_json: str) -> str`
  - `apply_template(project_json: str, template_id: str) -> str`
  - `render_preview(project_json: str, output_png: str, max_px: int = 1600) -> dict`
  - `export_cover(project_json: str, pdf_path: str, docx_path: str, dpi: int = 300) -> dict`
- Android bridge prefixes these as `cover_*` and returns JSON strings where Kotlin needs a single primitive return value.

- [ ] **Step 1: Write failing end-to-end service tests**

```python
def test_service_creates_previews_and_both_exports(epub_fixture, tmp_path):
    settings = json.dumps({
        "working_dir": str(tmp_path / "work"),
        "trim_width_mm": 105.0,
        "trim_height_mm": 148.0,
        "page_count": 160,
        "paper_caliper_mm": 0.10,
        "bleed_mm": 3.0,
        "overlap_mm": 5.0,
    })
    project_json = new_project(str(epub_fixture), settings)
    project_json = apply_template(project_json, "minimal_text")
    preview = render_preview(project_json, str(tmp_path / "preview.png"), 900)
    exports = export_cover(
        project_json,
        str(tmp_path / "cover.pdf"),
        str(tmp_path / "cover.docx"),
        300,
    )
    assert preview["width_px"] <= 900
    assert Path(exports["pdf"]["path"]).is_file()
    assert Path(exports["docx"]["path"]).is_file()
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest \
  python-tests/cover/test_service.py python-tests/test_android_bridge.py -q
```

Expected: FAIL because service functions are missing.

- [ ] **Step 3: Implement service input validation and working assets**

`new_project` must require a writable `working_dir`, copy/extract the selected embedded cover into `working_dir/assets`, sanitize generated filenames, and never write beside the source document. It must accept actual `page_count` from conversion completion; when absent for EPUB it estimates and marks the metadata estimate flag; when absent for DOCX/PDF it uses the fixed count or raises a clear validation error.

```python
def _writable_working_dir(value: object) -> Path:
    path = Path(str(value)).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write-probe"
    try:
        probe.write_bytes(b"ok")
    except OSError as exc:
        raise CoverValidationError("工作目錄不可寫入。") from exc
    finally:
        probe.unlink(missing_ok=True)
    return path


def _resolve_page_count(
    inspection: CoverMetadataInspection,
    settings: dict[str, object],
    source_path: Path,
) -> tuple[int, bool]:
    supplied = settings.get("page_count")
    if supplied is not None:
        count = int(supplied)
        if count <= 0:
            raise CoverValidationError("頁數必須大於 0。")
        return count, False
    if inspection.fixed_page_count is not None:
        return inspection.fixed_page_count, False
    if source_path.suffix.lower() == ".epub":
        return estimate_epub_page_count(source_path, LayoutSettings()), True
    raise CoverValidationError("無法自動取得頁數，請輸入並確認正文頁數。")


def _copy_asset(source: Path, assets_dir: Path) -> Path:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", source.name).strip("._") or "cover-image"
    destination = assets_dir / f"{digest}-{safe_name}"
    shutil.copyfile(source, destination)
    return destination.resolve()
```

- [ ] **Step 4: Add bridge wrappers without duplicating business logic**

Add to `android_bridge.py`:

```python
def cover_inspect_source_json(source_path: str) -> str:
    return json.dumps(inspect_source(source_path), ensure_ascii=False, separators=(",", ":"))


def cover_new_project_json(source_path: str, settings_json: str) -> str:
    return new_project(source_path, settings_json)


def cover_apply_template_json(project_json: str, template_id: str) -> str:
    return apply_template(project_json, template_id)


def cover_render_preview_json(project_json: str, output_png: str, max_px: int = 1600) -> str:
    return json.dumps(render_preview(project_json, output_png, max_px), ensure_ascii=False, separators=(",", ":"))


def cover_export_json(project_json: str, pdf_path: str, docx_path: str, dpi: int = 300) -> str:
    return json.dumps(export_cover(project_json, pdf_path, docx_path, dpi), ensure_ascii=False, separators=(",", ":"))
```

- [ ] **Step 5: Run all Python tests and commit**

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
git add python/src/epub_a4_word/cover app/src/main/python/android_bridge.py python-tests
git commit -m "feat: expose shared cover service API"
```

Expected: zero failures.

---

### Task 10: Add golden-file QA and core documentation

**Files:**
- Create: `python-tests/cover/test_golden_exports.py`
- Create: `scripts/inspect_cover_exports.py`
- Create: `scripts/compare_cover_geometry.py`
- Create: `docs/cover-project-schema-v1.md`
- Modify: `README.md`
- Modify: `BUILD_STATUS.md`

**Interfaces:**
- Produces deterministic geometry snapshot JSON used by desktop and Android acceptance tests.
- Produces CLI inspection output for PDF MediaBoxes, DOCX sections, anchored pictures, text boxes, and file sizes.

- [ ] **Step 1: Create one deterministic golden project fixture**

Use A5 trim, 160 pages, 80 gsm (`0.10 mm`), 3 mm bleed, 5 mm overlap, manual spine unset, full-spread image, title, author, description, publisher, and ISBN placeholder. Store project JSON under `python-tests/fixtures/cover/golden-project.json`; generate the referenced PNG in the test fixture to keep the JSON path portable.

```python
@pytest.fixture
def golden_project(tmp_path: Path) -> CoverProject:
    image_path = tmp_path / "golden-background.png"
    Image.new("RGB", (2400, 1800), (225, 225, 225)).save(image_path)
    payload = json.loads(
        Path("python-tests/fixtures/cover/golden-project.json").read_text("utf-8")
    )
    payload["source_file"] = str(tmp_path / "body.epub")
    payload["working_dir"] = str(tmp_path)
    for element in payload["elements"]:
        if element["kind"] == "image":
            element["content"]["path"] = str(image_path)
    return loads_project(json.dumps(payload, ensure_ascii=False))
```

The committed JSON must contain these exact physical values:

```json
{
  "schema_version": 1,
  "trim_size_mm": {"width_mm": 148.0, "height_mm": 210.0},
  "page_count": 160,
  "paper_caliper_mm": 0.1,
  "manual_spine_width_mm": null,
  "bleed_mm": 3.0,
  "overlap_mm": 5.0,
  "image_mode": "full_spread"
}
```

- [ ] **Step 2: Add structural golden assertions**

The test must assert:

```python
assert layout.spine_width_mm == pytest.approx(8.0)
assert print_plan.mode == "split"
assert [p.name for p in print_plan.pages] == ["back", "spine", "front"]
assert pdf_result.page_count == 3
assert docx_result.page_count == 3
assert docx_anchor_count >= 3
assert docx_text_box_count >= 5
```

- [ ] **Step 3: Implement geometry snapshot comparison**

`scripts/compare_cover_geometry.py` accepts two JSON files and `--tolerance-mm`; recursively compare numeric values whose keys end in `_mm`, print the maximum delta and failing path, and exit `1` when delta exceeds tolerance.

```python
def collect_mm_values(value: object, path: str = "$") -> dict[str, float]:
    found: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.endswith("_mm") and isinstance(child, (int, float)):
                found[child_path] = float(child)
            found.update(collect_mm_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(collect_mm_values(child, f"{path}[{index}]"))
    return found


def compare(left: dict[str, float], right: dict[str, float], tolerance: float) -> int:
    if left.keys() != right.keys():
        missing = sorted(left.keys() ^ right.keys())
        print("Geometry keys differ:", ", ".join(missing))
        return 1
    deltas = {key: abs(left[key] - right[key]) for key in left}
    worst_path, worst_delta = max(deltas.items(), key=lambda item: item[1], default=("$", 0.0))
    print(f"maximum delta={worst_delta:.6f} mm at {worst_path}")
    return 0 if worst_delta <= tolerance else 1
```

- [ ] **Step 4: Run the complete core gate**

```bash
python3.13 -m pip install -e '.[test]'
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
PYTHONPATH=python/src:app/src/main/python python3.13 -m compileall -q \
  python/src app/src/main/python
python3.13 scripts/verify_project.py
```

Expected: zero failures, successful compileall, successful project verification.

- [ ] **Step 5: Commit the completed core plan**

```bash
git add python-tests/cover scripts/inspect_cover_exports.py \
  scripts/compare_cover_geometry.py docs/cover-project-schema-v1.md \
  README.md BUILD_STATUS.md
git commit -m "test: add full-cover export acceptance gate"
```
