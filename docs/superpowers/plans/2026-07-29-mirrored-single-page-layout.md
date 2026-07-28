# Mirrored Single-Page Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mirror all single-page DOCX layouts so odd pages align right, even pages align left, and B6-on-A5 crop lines follow the same parity.

**Architecture:** Add page parity to the shared page-placement geometry, then render each single output page in its own fixed-width one-row table. Move B6 crop guides from a repeating section header to page-local anchor paragraphs so each page can carry different coordinates without creating a section per page.

**Tech Stack:** Python 3.13, python-docx, OOXML VML/DrawingML, lxml, pytest

## Global Constraints

- Apply to `single_a5`, `single_4x6`, and `b6_on_a5` only.
- Odd logical pages align right; even logical pages align left.
- Use the one-based physical output page number only when `MiniPage.logical_page_number` is absent.
- Content width, height, internal margins, font sizes, image sizes, and vertical position do not change.
- Existing page-number alignment continues to use `binding_direction`.
- B6 odd pages use the vertical crop guide at `20 mm`; B6 even pages use it at `128 mm`; both use the horizontal guide at `28 mm`.
- `single_a5` and `single_4x6` do not gain crop guides.
- Four-up and signature imposition remain unchanged.
- Desktop and Android use the same shared Python implementation.

---

### Task 1: Make page-placement geometry parity-aware

**Files:**
- Modify: `python/src/epub_a4_word/page_placement.py:30-83`
- Modify: `python-tests/test_page_placement.py:8-42`

**Interfaces:**
- Consumes: resolved or unresolved `LayoutSettings`
- Produces: `build_page_placement(settings: LayoutSettings, page_number: int = 1) -> PagePlacement`
- The default `page_number=1` preserves odd-page behavior for existing callers until Task 3 passes explicit page numbers.

- [ ] **Step 1: Write failing geometry tests for all three single-page modes**

Replace the fixed B6-only placement assertions with literal, parity-aware expectations:

```python
@pytest.mark.parametrize(
    ("mode", "odd_x", "even_x", "width"),
    [
        ("single_a5", 4.0, 0.0, 144.0),
        ("single_4x6", 4.0, 0.0, 97.6),
        ("b6_on_a5", 20.0, 0.0, 128.0),
    ],
)
def test_single_page_modes_mirror_horizontal_placement(
    mode: str,
    odd_x: float,
    even_x: float,
    width: float,
) -> None:
    settings = _resolved(mode)

    odd = build_page_placement(settings, page_number=1)
    even = build_page_placement(settings, page_number=2)

    assert (odd.content_x_mm, odd.content_width_mm) == pytest.approx(
        (odd_x, width)
    )
    assert (even.content_x_mm, even.content_width_mm) == pytest.approx(
        (even_x, width)
    )
    assert odd.content_y_mm == pytest.approx(even.content_y_mm)
    assert odd.content_height_mm == pytest.approx(even.content_height_mm)
```

Add the B6 guide parity test:

```python
def test_b6_crop_guides_follow_page_parity() -> None:
    settings = _resolved("b6_on_a5", output_mark_mode="crop_marks")

    odd = build_page_placement(settings, page_number=1)
    even = build_page_placement(settings, page_number=2)

    assert odd.guides == (
        CropGuide(0.0, 28.0, 148.0, 28.0, "crop"),
        CropGuide(20.0, 0.0, 20.0, 210.0, "crop"),
    )
    assert even.guides == (
        CropGuide(0.0, 28.0, 148.0, 28.0, "crop"),
        CropGuide(128.0, 0.0, 128.0, 210.0, "crop"),
    )
```

- [ ] **Step 2: Run the geometry tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/test_page_placement.py -q
```

Expected: tests error because `build_page_placement` does not accept `page_number`, proving the production interface lacks parity.

- [ ] **Step 3: Implement parity-aware horizontal placement**

Add a shared single-page mode set and extend the function signature:

```python
_SINGLE_PAGE_MODES = frozenset({"single_a5", "single_4x6", "b6_on_a5"})


def build_page_placement(
    settings: LayoutSettings,
    page_number: int = 1,
) -> PagePlacement:
    if page_number < 1:
        raise ValueError("page_number must be positive")
```

After computing `content_width`, place single-page content from literal paper geometry rather than a fixed left margin:

```python
    if resolved.imposition_mode in _SINGLE_PAGE_MODES:
        horizontal_slack = max(0.0, paper_width - content_width)
        content_x = horizontal_slack if page_number % 2 == 1 else 0.0
```

For B6 crop marks, place the vertical guide on the boundary between the content block and the blank side:

```python
        vertical_guide_x = (
            content_x
            if page_number % 2 == 1
            else content_x + content_width
        )
        guides.extend(
            (
                CropGuide(0.0, content_y, paper_width, content_y, "crop"),
                CropGuide(
                    vertical_guide_x,
                    0.0,
                    vertical_guide_x,
                    paper_height,
                    "crop",
                ),
            )
        )
```

Do not modify grid-mode guide calculations.

- [ ] **Step 4: Run geometry tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/test_page_placement.py -q
```

Expected: all page-placement tests pass.

- [ ] **Step 5: Commit the geometry contract**

```powershell
git add python/src/epub_a4_word/page_placement.py python-tests/test_page_placement.py
git commit -m "feat: mirror single-page placement geometry"
```

### Task 2: Write page-local crop guides

**Files:**
- Modify: `python/src/epub_a4_word/crop_marks.py:82-143`
- Modify: `python-tests/test_drawingml_page_guides.py:20-57`

**Interfaces:**
- Consumes: a real python-docx `Paragraph`, a sequence of `CropGuide`, page dimensions, stroke width, render mode, and starting drawing identifier
- Produces: `add_guides_to_paragraph(paragraph, guides, *, paper_width_mm, paper_height_mm, stroke_pt=0.35, render_mode="vml", identifier_start=1) -> None`
- Preserves: `add_page_guides(section, guides, ...) -> None`, now delegating serialization to the new paragraph-level function.

- [ ] **Step 1: Add a failing DrawingML paragraph-level guide test**

Add a test that writes two different guide sets into two body paragraphs and inspects the real DOCX:

```python
def test_page_local_drawingml_guides_keep_distinct_coordinates(tmp_path: Path) -> None:
    document = Document()
    odd = document.add_paragraph()
    even = document.add_paragraph()
    add_guides_to_paragraph(
        odd,
        (CropGuide(20.0, 0.0, 20.0, 210.0),),
        paper_width_mm=148.0,
        paper_height_mm=210.0,
        render_mode="drawingml",
        identifier_start=1,
    )
    add_guides_to_paragraph(
        even,
        (CropGuide(128.0, 0.0, 128.0, 210.0),),
        paper_width_mm=148.0,
        paper_height_mm=210.0,
        render_mode="drawingml",
        identifier_start=11,
    )
    output = tmp_path / "page-local-guides.docx"
    document.save(output)

    with ZipFile(output) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert xml.count("<w:drawing") == 2
    assert f"<wp:posOffset>{20 * 36000}</wp:posOffset>" in xml
    assert f"<wp:posOffset>{128 * 36000}</wp:posOffset>" in xml
    assert 'name="epub2a4-crop-guide-1"' in xml
    assert 'name="epub2a4-crop-guide-11"' in xml
```

Import `Document`, `CropGuide`, and `add_guides_to_paragraph` in the test.

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/test_drawingml_page_guides.py::test_page_local_drawingml_guides_keep_distinct_coordinates -q
```

Expected: collection fails because `add_guides_to_paragraph` does not exist.

- [ ] **Step 3: Extract the paragraph-level serializer**

Move guide validation and run creation from `add_page_guides` into:

```python
def add_guides_to_paragraph(
    paragraph,
    guides: Sequence[CropGuide],
    *,
    paper_width_mm: float,
    paper_height_mm: float,
    stroke_pt: float = 0.35,
    render_mode: str = "vml",
    identifier_start: int = 1,
) -> None:
    if identifier_start < 1:
        raise ValueError("identifier_start must be positive")
    # Retain the existing stroke, render-mode, guide-role, and bounds checks.
    if not guides:
        return
    install_story_template_fallbacks()
    paragraph.paragraph_format.space_before = 0
    paragraph.paragraph_format.space_after = 0
    paragraph.paragraph_format.line_spacing = 1
    for identifier, guide in enumerate(guides, start=identifier_start):
        run = paragraph.add_run()
        xml = (
            _drawing_line_xml(identifier, guide, stroke_pt)
            if render_mode == "drawingml"
            else _line_xml(identifier, guide, stroke_pt)
        )
        run._r.append(parse_xml(xml))
```

Keep `add_page_guides` as the existing header API:

```python
    if not guides:
        return
    header = section.header
    header.is_linked_to_previous = False
    add_guides_to_paragraph(
        header.paragraphs[0],
        guides,
        paper_width_mm=paper_width_mm,
        paper_height_mm=paper_height_mm,
        stroke_pt=stroke_pt,
        render_mode=render_mode,
    )
```

- [ ] **Step 4: Run all crop-guide tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/test_drawingml_page_guides.py python-tests/test_docx_page_guides.py -q
```

Expected: all VML, DrawingML, crop, and fold guide tests pass.

- [ ] **Step 5: Commit the reusable guide writer**

```powershell
git add python/src/epub_a4_word/crop_marks.py python-tests/test_drawingml_page_guides.py
git commit -m "refactor: support page-local crop guides"
```

### Task 3: Render one mirrored table per single output page

**Files:**
- Modify: `python/src/epub_a4_word/docx_writer.py:13-24,326-429`
- Modify: `python-tests/core/test_docx_writer.py:193-224`
- Modify: `python-tests/test_docx_page_guides.py:20-108`
- Modify: `python-tests/test_b6_blank_page_regression.py:23-46`
- Modify: `python-tests/test_single_page_blank_page_regression.py:23-74`

**Interfaces:**
- Consumes: `build_page_placement(settings, page_number)` from Task 1 and `add_guides_to_paragraph(...)` from Task 2
- Produces: unchanged public API `write_docx(...) -> list[str]`

- [ ] **Step 1: Write failing DOCX structure tests**

Add a reusable three-page call in `python-tests/core/test_docx_writer.py` and assert the user-visible table alignment:

```python
@pytest.mark.parametrize(
    "mode",
    ["single_a5", "single_4x6", "b6_on_a5"],
)
def test_single_page_modes_mirror_each_page_table(mode: str, tmp_path: Path) -> None:
    output = tmp_path / f"{mode}-mirrored.docx"
    pages = [
        MiniPage(
            [TextBlock((TextRun(f"第 {number} 頁"),), style="body")],
            logical_page_number=number,
        )
        for number in (1, 2, 3)
    ]

    write_docx(
        pages,
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode=mode,
            page_numbers=False,
        ),
        imposition_mode=mode,
    )

    document = Document(output)
    assert len(document.tables) == 3
    assert [table.alignment for table in document.tables] == [
        WD_TABLE_ALIGNMENT.RIGHT,
        WD_TABLE_ALIGNMENT.LEFT,
        WD_TABLE_ALIGNMENT.RIGHT,
    ]
    assert [
        table.cell(0, 0).text
        for table in document.tables
    ] == ["第 1 頁", "第 2 頁", "第 3 頁"]
```

Update `test_single_page_modes_use_one_multirow_table_without_prefix_paragraphs`
to describe the new structure and require three one-row tables and exactly two
`w:pageBreakBefore` markers for three input pages:

```python
    body = root.find(f"{{{W_NS}}}body")
    assert body is not None
    assert [etree.QName(child).localname for child in body] == [
        "p", "tbl", "p", "tbl", "p", "tbl", "sectPr"
    ]
    assert int(root.xpath(
        "count(.//w:body/w:tbl)",
        namespaces={"w": W_NS},
    )) == 3
    assert int(root.xpath(
        "count(.//w:pageBreakBefore)",
        namespaces={"w": W_NS},
    )) == 2
```

Make the equivalent two-page expectation in
`test_b6_uses_one_multirow_table_without_standalone_prefix_paragraphs`:

```python
    assert top_level == ["p", "tbl", "p", "tbl", "sectPr"]
    assert int(document.xpath(
        "count(.//w:body/w:tbl)",
        namespaces={"w": W_NS},
    )) == 2
    assert int(document.xpath(
        "count(.//w:pageBreakBefore)",
        namespaces={"w": W_NS},
    )) == 1
```

- [ ] **Step 2: Add failing per-page B6 guide assertions**

Update `_page` in `python-tests/test_docx_page_guides.py` to accept
`number: int = 1`. Split the existing line parser into literal helpers that
inspect either story:

```python
def _lines_from_payload(payload: bytes):
    return [
        (
            tuple(float(value) for value in match.groups()[:5]),
            match.group(6),
        )
        for match in _LINE_RE.finditer(payload)
    ]


def _lines_from_headers(path: Path):
    return _lines_from_payload(_header_xml(path))


def _lines_from_document(path: Path):
    with ZipFile(path) as archive:
        return _lines_from_payload(archive.read("word/document.xml"))
```

Rename existing `_lines(...)` calls to `_lines_from_headers(...)`. Then write
two B6 pages and inspect `word/document.xml`:

```python
def test_b6_docx_mirrors_crop_lines_per_page(tmp_path: Path) -> None:
    output = tmp_path / "b6-mirrored-guides.docx"
    pages = [_page("奇數頁", 1), _page("偶數頁", 2)]
    write_docx(
        pages,
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode="b6_on_a5",
            output_mark_mode="crop_marks",
        ),
        imposition_mode="b6_on_a5",
    )

    lines = _lines_from_document(output)
    assert len(lines) == 4
    vertical_x = [
        values[0]
        for values, _inner in lines
        if values[0] == values[2]
    ]
    assert vertical_x == pytest.approx(
        [20.0 * 72.0 / 25.4, 128.0 * 72.0 / 25.4],
        abs=0.01,
    )
    assert _lines_from_headers(output) == []
```

Keep existing assertions that disabled marks produce no guide objects.

- [ ] **Step 3: Run the new writer tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/core/test_docx_writer.py::test_single_page_modes_mirror_each_page_table python-tests/test_docx_page_guides.py::test_b6_docx_mirrors_crop_lines_per_page python-tests/test_b6_blank_page_regression.py -q
```

Expected: FAIL because the writer still emits one centered multi-row table and repeating header guides.

- [ ] **Step 4: Implement per-page single-mode tables**

Import the new paragraph-level guide writer:

```python
from .crop_marks import add_guides_to_paragraph, add_page_guides
```

For single-page modes, set section left and right margins to zero while leaving top and bottom unchanged:

```python
    if imposition_mode in _SINGLE_PAGE_TABLE_MODES:
        section.left_margin = Cm(0)
        section.right_margin = Cm(0)
```

Only install repeating header guides for grid modes:

```python
    if imposition_mode not in _SINGLE_PAGE_TABLE_MODES:
        add_page_guides(
            section,
            placement.guides,
            paper_width_mm=placement.paper_width_mm,
            paper_height_mm=placement.paper_height_mm,
            render_mode=settings.guide_render_mode,
        )
```

Replace the one-table single-mode branch with one table and one page-local prefix paragraph per page:

```python
    if imposition_mode in _SINGLE_PAGE_TABLE_MODES:
        first_prefix = document.add_paragraph()
        for side_index, slots in enumerate(plan.sides):
            prefix = (
                first_prefix
                if side_index == 0
                else document.add_paragraph()
            )
            _configure_page_prefix(
                prefix,
                page_break_before=side_index > 0,
            )
            physical_page_number = slots[0]
            page = (
                pages[physical_page_number - 1]
                if physical_page_number is not None
                else None
            )
            parity_number = (
                page.logical_page_number
                if page is not None and page.logical_page_number is not None
                else side_index + 1
            )
            page_placement = build_page_placement(
                settings,
                page_number=parity_number,
            )
            add_guides_to_paragraph(
                prefix,
                page_placement.guides,
                paper_width_mm=page_placement.paper_width_mm,
                paper_height_mm=page_placement.paper_height_mm,
                render_mode=settings.guide_render_mode,
                identifier_start=side_index * 10 + 1,
            )

            table = document.add_table(rows=1, cols=1)
            configure_table(table)
            table.alignment = (
                WD_TABLE_ALIGNMENT.RIGHT
                if parity_number % 2 == 1
                else WD_TABLE_ALIGNMENT.LEFT
            )
            row = table.rows[0]
            configure_row(row)
            warnings.extend(
                _populate_cell(
                    row.cells[0],
                    page,
                    0,
                    1,
                    settings,
                    resources,
                    media_types,
                )
            )
```

Make every page-local prefix exactly one OOXML twip high from the start, so the
anchor remains present without reserving a visible one-point line. Reuse the
existing `OxmlElement` and `qn` imports, and replace the current one-point
paragraph/run formatting in `_configure_page_prefix` with:

```python
    fmt = paragraph.paragraph_format
    fmt.page_break_before = page_break_before
    p_pr = paragraph._p.get_or_add_pPr()
    spacing = p_pr.find(qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        p_pr.append(spacing)
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "1")
    spacing.set(qn("w:lineRule"), "exact")
    run = paragraph.add_run("\u200b")
    run.font.size = Pt(0.5)
```

Keep the existing multi-page grid branch unchanged. Do not reduce table height,
content dimensions, images, or typography to make room for the prefix.

- [ ] **Step 5: Run single-page writer tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests/core/test_docx_writer.py python-tests/test_docx_page_guides.py python-tests/test_b6_blank_page_regression.py python-tests/test_single_page_blank_page_regression.py python-tests/test_b6_on_a5.py -q
```

Expected: all single-page, guide, page-number, image, and blank-page regressions pass.

- [ ] **Step 6: Commit the mirrored writer**

```powershell
git add python/src/epub_a4_word/docx_writer.py python-tests/core/test_docx_writer.py python-tests/test_docx_page_guides.py python-tests/test_b6_blank_page_regression.py python-tests/test_single_page_blank_page_regression.py
git commit -m "feat: mirror odd and even single pages"
```

### Task 4: Verify Desktop and Android integration

**Files:**
- Verify only: `python-tests`
- Verify only: `desktop/tests`
- Verify only: `app/src/test`

**Interfaces:**
- Consumes: unchanged conversion settings and `write_docx(...)`
- Produces: no new interface; verifies the shared implementation reaches Desktop and Android without model changes

- [ ] **Step 1: Run the complete Python suite**

```powershell
.\.venv\Scripts\python.exe -m pytest python-tests -q
```

Expected: all non-environment-skipped tests pass.

- [ ] **Step 2: Run the complete Desktop suite**

```powershell
.\.venv\Scripts\python.exe -m pytest desktop\tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Run the Android unit suite**

```powershell
$env:ANDROID_HOME='C:\Users\fadai\AppData\Local\Android\Sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
& "$env:USERPROFILE\.gradle\wrapper\dists\gradle-9.1.0-bin\9agqghryom9wkf8r80qlhnts3\gradle-9.1.0\bin\gradle.bat" --no-daemon :app:testDebugUnitTest
```

Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Verify repository scope**

```powershell
git diff --check
git status --short
git log --oneline main..HEAD
```

Expected: no tracked modifications remain; the pre-existing untracked `uv.lock` is not staged or committed.
