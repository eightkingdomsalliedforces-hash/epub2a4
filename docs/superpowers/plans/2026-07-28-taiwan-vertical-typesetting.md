# Taiwan Vertical Typesetting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add selectable Taiwan-style vertical/right-bound and horizontal/left-bound conversion to the shared Python core, Windows Desktop, and Android while preserving images, mixed-language text, and the existing page-number switch.

**Architecture:** `LayoutSettings` remains the single source of truth. Shared Python code validates the two new wire values, paginates vertical text by column capacity, mirrors physical placement for right binding, and emits native OOXML `tbRl`; Desktop and Android only select and transmit the paired presets. Existing callers which omit both fields retain horizontal/left behavior, while new UI requests default to vertical/right.

**Tech Stack:** Python 3.13, dataclasses, python-docx/WordprocessingML, pytest, PySide6/pytest-qt, Kotlin, Jetpack Compose, Chaquopy, JUnit

## Global Constraints

- Target version is `v0.8.0`.
- Supported platforms are Windows Desktop, Android, and the shared Python core.
- Valid wire values are `writing_mode = "taiwan_vertical" | "horizontal"` and `binding_direction = "right" | "left"`.
- Missing shared-core fields default to `horizontal` and `left` for backward compatibility.
- New Desktop and Android requests default to `taiwan_vertical` and `right`.
- The current UI exposes only the paired presets Taiwan vertical/right-bound and horizontal/left-bound.
- Chinese remains upright; English and long numbers follow Microsoft Word native vertical behavior.
- Images remain upright and retain document order.
- The existing single page-number switch controls every numbered text and image-only page.
- Pages before the existing numbering start remain unnumbered.
- Horizontal/left golden behavior must remain unchanged.
- Unsupported writing or binding values raise explicit errors.

---

### Task 1: Shared layout settings and validation contract

**Files:**
- Modify: `python/src/epub_a4_word/models.py`
- Modify: `python/src/epub_a4_word/pagination.py`
- Test: `python-tests/core/test_pagination.py`

**Interfaces:**
- Produces in `models.py`: `WritingMode = Literal["taiwan_vertical", "horizontal"]`
- Produces in `models.py`: `BindingDirection = Literal["right", "left"]`
- Produces: `LayoutSettings.writing_mode: WritingMode = "horizontal"`
- Produces: `LayoutSettings.binding_direction: BindingDirection = "left"`
- Produces: `validate_layout_modes(settings: LayoutSettings) -> None`
- Consumed by: pagination, imposition, DOCX writers, Desktop requests, and Android bridge tasks.

- [ ] **Step 1: Write failing validation/default tests**

```python
def test_layout_direction_defaults_preserve_legacy_horizontal_behavior() -> None:
    settings = LayoutSettings()
    assert settings.writing_mode == "horizontal"
    assert settings.binding_direction == "left"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("writing_mode", "diagonal", "writing mode"),
        ("binding_direction", "middle", "binding direction"),
    ],
)
def test_resolve_layout_rejects_unknown_direction_values(field, value, message) -> None:
    settings = replace(LayoutSettings(), **{field: value})
    with pytest.raises(ValueError, match=message):
        resolve_layout(settings)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest python-tests/core/test_pagination.py -k "direction_defaults or unknown_direction" -q`

Expected: FAIL because the fields and validation do not exist.

- [ ] **Step 3: Add the typed fields and strict validation**

```python
# models.py
WritingMode = Literal["taiwan_vertical", "horizontal"]
BindingDirection = Literal["right", "left"]


# pagination.py
@dataclass(frozen=True)
class LayoutSettings:
    writing_mode: WritingMode = "horizontal"
    binding_direction: BindingDirection = "left"


def validate_layout_modes(settings: LayoutSettings) -> None:
    if settings.writing_mode not in {"taiwan_vertical", "horizontal"}:
        raise ValueError(f"Unsupported writing mode: {settings.writing_mode}")
    if settings.binding_direction not in {"right", "left"}:
        raise ValueError(
            f"Unsupported binding direction: {settings.binding_direction}"
        )
```

Insert these fields after `imposition_mode`; leave the existing margin,
font, sizing, page-number, guide, paper, grid, and page-margin fields
unchanged.

Call `validate_layout_modes(settings)` at the start of `resolve_layout`.

- [ ] **Step 4: Run the focused and complete pagination tests**

Run: `python -m pytest python-tests/core/test_pagination.py -q`

Expected: PASS, including all legacy margin and capacity tests.

- [ ] **Step 5: Commit the shared contract**

```bash
git add python/src/epub_a4_word/models.py python/src/epub_a4_word/pagination.py python-tests/core/test_pagination.py
git commit -m "feat: add writing and binding layout settings"
```

---

### Task 2: Vertical column capacity and lossless pagination

**Files:**
- Modify: `python/src/epub_a4_word/pagination.py`
- Test: `python-tests/core/test_pagination.py`

**Interfaces:**
- Consumes: `LayoutSettings.writing_mode`
- Produces: `_page_capacity_points(settings: LayoutSettings) -> float`
- Produces: `_vertical_chars_per_column(block: TextBlock, settings: LayoutSettings) -> float`
- Produces: `_vertical_column_advance(block: TextBlock, settings: LayoutSettings) -> float`
- Produces: `_validate_vertical_capacity(block: TextBlock, settings: LayoutSettings) -> None`
- Existing public interface preserved: `paginate(...) -> list[MiniPage]`

- [ ] **Step 1: Write failing vertical pagination tests**

```python
def test_vertical_pagination_keeps_mixed_text_in_source_order() -> None:
    text = "魔法禁書目錄 A Certain Magical Index 2026。" * 90
    settings = LayoutSettings(
        writing_mode="taiwan_vertical",
        binding_direction="right",
        content_width_pt=120,
        content_height_pt=220,
        page_numbers=False,
    )
    pages = paginate([_body(text)], settings, image_sizes={})
    rebuilt = "".join(
        block.text
        for page in pages
        for block in page.blocks
        if isinstance(block, TextBlock)
    )
    assert len(pages) > 1
    assert rebuilt == text
    assert all(page.used_points <= settings.content_width_pt + 0.01 for page in pages)


def test_vertical_page_capacity_uses_height_for_characters_and_width_for_columns() -> None:
    tall = LayoutSettings(
        writing_mode="taiwan_vertical",
        content_width_pt=120,
        content_height_pt=260,
        page_numbers=False,
    )
    short = replace(tall, content_height_pt=130)
    text = _body("直排容量測試。" * 120)
    assert len(paginate([text], tall, {})) < len(paginate([text], short, {}))


def test_vertical_pagination_rejects_a_page_that_cannot_fit_one_character() -> None:
    settings = LayoutSettings(
        writing_mode="taiwan_vertical",
        content_width_pt=4,
        content_height_pt=4,
        body_font_pt=9,
        page_numbers=False,
    )
    with pytest.raises(ValueError, match="直排版面"):
        paginate([_body("字")], settings, {})
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `python -m pytest python-tests/core/test_pagination.py -k vertical -q`

Expected: FAIL because horizontal line measurement is still used.

- [ ] **Step 3: Implement vertical measurement without rewriting source text**

```python
def _page_capacity_points(settings: LayoutSettings) -> float:
    resolved = resolve_layout(settings)
    if resolved.writing_mode == "taiwan_vertical":
        assert resolved.content_width_pt is not None
        return resolved.content_width_pt
    assert resolved.content_height_pt is not None
    return resolved.content_height_pt


def _vertical_chars_per_column(
    block: TextBlock,
    settings: LayoutSettings,
) -> float:
    assert settings.content_height_pt is not None
    font_pt = _font_for(block, settings)
    return max(4.0, settings.content_height_pt / (font_pt * 1.07))


def _vertical_column_advance(
    block: TextBlock,
    settings: LayoutSettings,
) -> float:
    return _font_for(block, settings) * settings.line_spacing


def _validate_vertical_capacity(
    block: TextBlock,
    settings: LayoutSettings,
) -> None:
    assert settings.content_width_pt is not None
    assert settings.content_height_pt is not None
    font_pt = _font_for(block, settings)
    if settings.content_height_pt < font_pt or settings.content_width_pt < font_pt:
        raise ValueError("直排版面過小，無法安全放置一個字元。")
```

Branch `_estimated_line_count`, `measure_text`, `_find_split_index`, and
`paginate` on `writing_mode`. In vertical mode, count weighted characters per
column, return occupied column width, compare it with `_page_capacity_points`,
and continue to use `_split_runs_at` so bold/italic run boundaries and source
order are preserved.

- [ ] **Step 4: Add paragraph, heading, quote, break, and image-order coverage**

```python
def test_vertical_pagination_preserves_blocks_styles_and_explicit_breaks() -> None:
    blocks = [
        TextBlock((TextRun("第一章"),), style="heading"),
        _body("正文" * 100),
        TextBlock((TextRun("引文"),), style="quote"),
        PageBreakBlock(),
        ImageBlock("Images/plate.png"),
        _body("插圖後文字"),
    ]
    settings = LayoutSettings(
        writing_mode="taiwan_vertical",
        binding_direction="right",
        content_width_pt=150,
        content_height_pt=210,
        page_numbers=False,
    )
    pages = paginate(blocks, settings, {"Images/plate.png": (600, 900)})
    flattened = [block for page in pages for block in page.blocks]
    assert [block.style for block in flattened if isinstance(block, TextBlock)][0] == "heading"
    assert next(i for i, block in enumerate(flattened) if isinstance(block, ImageBlock)) < len(flattened) - 1
    assert flattened[-1].text == "插圖後文字"
```

- [ ] **Step 5: Run pagination tests**

Run: `python -m pytest python-tests/core/test_pagination.py -q`

Expected: PASS with horizontal goldens unchanged.

- [ ] **Step 6: Commit vertical pagination**

```bash
git add python/src/epub_a4_word/pagination.py python-tests/core/test_pagination.py
git commit -m "feat: paginate Taiwan vertical text by columns"
```

---

### Task 3: Binding-aware imposition and page-number rules

**Files:**
- Modify: `python/src/epub_a4_word/imposition.py`
- Modify: `python/src/epub_a4_word/converter.py`
- Modify: `python/src/epub_a4_word/docx_writer.py`
- Test: `python-tests/core/test_imposition.py`
- Test: `python-tests/core/test_docx_writer.py`

**Interfaces:**
- Consumes: `BindingDirection`
- Changes: `build_imposition(page_count, mode="four_up", binding_direction="left")`
- Produces: `_page_number_alignment(page_number: int, binding_direction: BindingDirection)`
- Existing two-argument `build_imposition` calls keep left-binding output.

- [ ] **Step 1: Write failing right-binding imposition tests**

```python
def test_right_binding_mirrors_each_signature_row_without_reordering_pages() -> None:
    plan = build_imposition(16, "signature16", "right")
    assert plan.sides == (
        (1, 16, 3, 14),
        (15, 2, 13, 4),
        (5, 12, 7, 10),
        (11, 6, 9, 8),
    )
    assert sorted(page for side in plan.sides for page in side if page) == list(range(1, 17))


def test_right_binding_mirrors_four_up_rows() -> None:
    assert build_imposition(4, "four_up", "right").sides == ((2, 1, 4, 3),)


@pytest.mark.parametrize("mode", ["single_a5", "single_4x6", "b6_on_a5"])
def test_single_page_modes_keep_logical_order_for_right_binding(mode) -> None:
    assert build_imposition(3, mode, "right").sides == ((1,), (2,), (3,))
```

- [ ] **Step 2: Run imposition tests and verify failure**

Run: `python -m pytest python-tests/core/test_imposition.py -q`

Expected: FAIL because `build_imposition` has no binding argument.

- [ ] **Step 3: Implement row mirroring in the shared imposition core**

```python
def _mirror_rows(side: SideSlots, columns: int) -> SideSlots:
    return tuple(
        item
        for start in range(0, len(side), columns)
        for item in reversed(side[start : start + columns])
    )


def build_imposition(
    page_count: int,
    mode: ImpositionMode = "four_up",
    binding_direction: BindingDirection = "left",
) -> ImpositionPlan:
    if page_count < 0:
        raise ValueError("page_count must not be negative")
    if binding_direction not in {"left", "right"}:
        raise ValueError(f"Unsupported binding direction: {binding_direction}")
    if mode == "four_up":
        plan = _build_four_up(page_count)
    elif mode == "signature16":
        plan = _build_signature16(page_count)
    elif mode in {"single_a5", "single_4x6", "b6_on_a5"}:
        plan = _build_single_page(page_count, mode)
    else:
        raise ValueError(f"Unsupported imposition mode: {mode}")
    if binding_direction == "right" and mode in {"four_up", "signature16"}:
        return replace(
            plan,
            sides=tuple(_mirror_rows(side, 2) for side in plan.sides),
        )
    return plan
```

Import `BindingDirection` from `models.py`, which avoids the existing
`pagination -> imposition` import cycle. Pass `settings.binding_direction`
from `convert_epub` and `write_docx`.

- [ ] **Step 4: Replace the old image-page exclusion with the single switch rule**

Change:

```python
if settings.page_numbers and page.logical_page_number is not None and page.has_text:
```

to:

```python
if settings.page_numbers and page.logical_page_number is not None:
```

Add:

```python
def _page_number_alignment(page_number: int, binding_direction: str):
    odd_is_right = binding_direction == "left"
    align_right = (page_number % 2 == 1) == odd_is_right
    return WD_ALIGN_PARAGRAPH.RIGHT if align_right else WD_ALIGN_PARAGRAPH.LEFT
```

Use this helper in `_add_page_number`.

- [ ] **Step 5: Update the image-only and disabled-page-number writer tests**

```python
def test_writer_displays_logical_number_on_text_and_image_pages(tmp_path: Path) -> None:
    output = tmp_path / "logical-numbers.docx"
    text_page = MiniPage(
        [TextBlock((TextRun("序章正文"),), style="body")],
        logical_page_number=1,
    )
    image_page = MiniPage(
        [ImageBlock("Images/test.png")],
        logical_page_number=2,
    )
    image_data = BytesIO()
    Image.new("RGB", (200, 300), "white").save(image_data, format="PNG")
    write_docx(
        [text_page, image_page],
        output,
        resources={"Images/test.png": image_data.getvalue()},
        media_types={"Images/test.png": "image/png"},
        settings=LayoutSettings(page_numbers=True, imposition_mode="four_up"),
    )
    cells = [cell for row in Document(output).tables[0].rows for cell in row.cells]
    assert "1" in cells[0].text.splitlines()
    assert "2" in cells[1].text.splitlines()


def test_writer_page_number_switch_removes_numbers_from_all_page_types(tmp_path: Path) -> None:
    output = tmp_path / "no-logical-numbers.docx"
    pages = [
        MiniPage([TextBlock((TextRun("正文"),), style="body")], logical_page_number=1),
        MiniPage([ImageBlock("Images/test.png")], logical_page_number=2),
    ]
    image_data = BytesIO()
    Image.new("RGB", (200, 300), "white").save(image_data, format="PNG")
    write_docx(
        pages,
        output,
        resources={"Images/test.png": image_data.getvalue()},
        media_types={"Images/test.png": "image/png"},
        settings=LayoutSettings(page_numbers=False, imposition_mode="four_up"),
    )
    cells = [cell for row in Document(output).tables[0].rows for cell in row.cells]
    assert "1" not in cells[0].text.splitlines()
    assert "2" not in cells[1].text.splitlines()
```

Also add a focused unit assertion that right binding maps odd page `1` left
and even page `2` right, while left binding retains the opposite mapping.

- [ ] **Step 6: Run imposition, writer, and integration tests**

Run: `python -m pytest python-tests/core/test_imposition.py python-tests/core/test_docx_writer.py python-tests/core/test_integration.py -q`

Expected: PASS; image-only logical pages are now visible when the switch is on.

- [ ] **Step 7: Commit binding and page-number behavior**

```bash
git add python/src/epub_a4_word/imposition.py python/src/epub_a4_word/converter.py python/src/epub_a4_word/docx_writer.py python-tests/core/test_imposition.py python-tests/core/test_docx_writer.py
git commit -m "feat: support right binding and image page numbers"
```

---

### Task 4: Native vertical OOXML for EPUB output

**Files:**
- Modify: `python/src/epub_a4_word/docx_writer.py`
- Test: `python-tests/core/test_docx_writer.py`
- Test: `python-tests/core/test_integration.py`

**Interfaces:**
- Produces: `_set_cell_text_direction(cell, value: str) -> None`
- Produces: `_set_nested_cell_horizontal(cell) -> None`
- Consumes: `settings.writing_mode`
- Output contract: vertical content cells contain `<w:textDirection w:val="tbRl"/>`; horizontal cells do not.
- Output contract: vertical conversion returns one Microsoft Word/East Asia font compatibility warning.

- [ ] **Step 1: Write failing OOXML direction tests**

```python
def test_vertical_writer_emits_native_tb_rl_and_keeps_source_text(tmp_path: Path) -> None:
    output = tmp_path / "vertical.docx"
    text = "中文 English 2026"
    write_docx(
        [MiniPage([TextBlock((TextRun(text),), style="body")], logical_page_number=1)],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            writing_mode="taiwan_vertical",
            binding_direction="right",
            page_numbers=False,
        ),
    )
    with ZipFile(output) as archive:
        xml = archive.read("word/document.xml")
    assert b'<w:textDirection w:val="tbRl"' in xml
    assert text in Document(output).tables[0].cell(0, 0).text


def test_horizontal_writer_does_not_emit_vertical_text_direction(tmp_path: Path) -> None:
    output = tmp_path / "horizontal.docx"
    write_docx(
        [_page("中文 English 2026")],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            writing_mode="horizontal",
            binding_direction="left",
        ),
    )
    with ZipFile(output) as archive:
        assert b'<w:textDirection w:val="tbRl"' not in archive.read(
            "word/document.xml"
        )


def test_vertical_writer_returns_word_compatibility_warning(tmp_path: Path) -> None:
    warnings = write_docx(
        [_page("直排")],
        tmp_path / "warning.docx",
        resources={},
        media_types={},
        settings=LayoutSettings(writing_mode="taiwan_vertical"),
    )
    assert any("Microsoft Word" in warning and "East Asia" in warning for warning in warnings)
```

- [ ] **Step 2: Run the direction tests and verify failure**

Run: `python -m pytest python-tests/core/test_docx_writer.py -k "native_tb_rl or vertical_text_direction" -q`

Expected: FAIL because cells do not have `w:textDirection`.

- [ ] **Step 3: Add native cell direction**

```python
def _set_cell_text_direction(cell, value: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    node = tc_pr.find(qn("w:textDirection"))
    if node is None:
        node = OxmlElement("w:textDirection")
        tc_pr.append(node)
    node.set(qn("w:val"), value)
```

In `_populate_cell`, set `tbRl` only when
`settings.writing_mode == "taiwan_vertical"`. Preserve existing paragraph and
run construction so Word, not the application, rotates English and long
numbers. Do not split strings into one-character runs.

- [ ] **Step 4: Keep pictures and page numbers upright**

Write image and page-number content into a nested one-cell table whose cell
has `w:textDirection="lrTb"`:

```python
def _horizontal_container(parent_cell):
    table = parent_cell.add_table(rows=1, cols=1)
    _set_table_borders(table, False)
    nested = table.cell(0, 0)
    _set_cell_text_direction(nested, "lrTb")
    return nested
```

Use the horizontal container in `_add_image_block` and `_add_page_number`.
The picture relationship, width/height ratio, and page-number text remain
unchanged.

Append one stable warning in `write_docx` when vertical mode is active:

```python
warnings.append(
    "直排使用 Microsoft Word 原生格式；其他閱讀器或缺少 East Asia 字型時可能替代字形。"
)
```

- [ ] **Step 5: Add an upright-image relationship regression**

```python
def test_vertical_writer_keeps_image_in_horizontal_nested_cell(tmp_path: Path) -> None:
    image_data = BytesIO()
    Image.new("RGB", (200, 300), "white").save(image_data, format="PNG")
    output = tmp_path / "vertical-image.docx"
    write_docx(
        [MiniPage([ImageBlock("Images/test.png")], logical_page_number=1)],
        output,
        resources={"Images/test.png": image_data.getvalue()},
        media_types={"Images/test.png": "image/png"},
        settings=LayoutSettings(
            writing_mode="taiwan_vertical",
            binding_direction="right",
        ),
    )
    with ZipFile(output) as archive:
        xml = archive.read("word/document.xml")
        names = archive.namelist()
    assert b'<w:textDirection w:val="tbRl"' in xml
    assert b'<w:textDirection w:val="lrTb"' in xml
    assert len(Document(output).inline_shapes) == 1
    assert any(name.startswith("word/media/") for name in names)
```

- [ ] **Step 6: Verify the produced package reopens**

Run: `python -m pytest python-tests/core/test_docx_writer.py python-tests/core/test_integration.py -q`

Expected: PASS; `python-docx` reopens the output and image relationships remain valid.

- [ ] **Step 7: Commit native EPUB vertical output**

```bash
git add python/src/epub_a4_word/docx_writer.py python-tests/core/test_docx_writer.py python-tests/core/test_integration.py
git commit -m "feat: emit native vertical OOXML for EPUB pages"
```

---

### Task 5: Native vertical reflow for existing DOCX files

**Files:**
- Modify: `python/src/epub_a4_word/word_reflow.py`
- Test: `python-tests/core/test_word_reflow.py`

**Interfaces:**
- Produces: `_set_section_text_direction(section, value: str | None) -> None`
- Consumes: `LayoutSettings.writing_mode`, `LayoutSettings.binding_direction`
- Preserves: paragraphs, runs, tables, images, manual page breaks, package relationships.
- Extends DOCX single-page support to the already exposed `b6_on_a5` mode.

- [ ] **Step 1: Write a failing mixed-content DOCX regression**

```python
def test_convert_docx_vertical_sets_tb_rl_without_losing_content(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    output = tmp_path / "vertical.docx"
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("中文").bold = True
    paragraph.add_run(" English 2026").italic = True
    document.add_picture(str(_make_png(tmp_path)))
    document.add_page_break()
    document.add_paragraph("第二頁")
    document.save(source)

    convert_docx(
        source,
        output,
        LayoutSettings(
            imposition_mode="single_a5",
            writing_mode="taiwan_vertical",
            binding_direction="right",
        ),
    )

    reopened = Document(output)
    assert [p.text for p in reopened.paragraphs if p.text] == [
        "中文 English 2026",
        "第二頁",
    ]
    assert reopened.paragraphs[0].runs[0].bold is True
    assert reopened.paragraphs[0].runs[1].italic is True
    assert len(reopened.inline_shapes) == 1
    with ZipFile(output) as archive:
        assert b'<w:textDirection w:val="tbRl"' in archive.read("word/document.xml")


def test_convert_docx_accepts_vertical_b6_on_a5(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    output = tmp_path / "b6.docx"
    document = Document()
    document.add_paragraph("B6 直排正文")
    document.save(source)
    result = convert_docx(
        source,
        output,
        LayoutSettings(
            imposition_mode="b6_on_a5",
            writing_mode="taiwan_vertical",
            binding_direction="right",
        ),
    )
    assert result.imposition_mode == "b6_on_a5"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest python-tests/core/test_word_reflow.py -k vertical -q`

Expected: FAIL because no section direction is written.

- [ ] **Step 3: Apply native section direction and mirrored page fields**

```python
def _set_section_text_direction(section, value: str | None) -> None:
    sect_pr = section._sectPr
    node = sect_pr.find(qn("w:textDirection"))
    if value is None:
        if node is not None:
            sect_pr.remove(node)
        return
    if node is None:
        node = OxmlElement("w:textDirection")
        sect_pr.append(node)
    node.set(qn("w:val"), value)
```

Call it for every section with `tbRl` in vertical mode and `None` in
horizontal mode. Configure odd/even footer stories when page numbers are
enabled so right binding mirrors the existing left-binding outside edge.
Keep page fields horizontal and readable.

Change `_SUPPORTED_MODES` to
`{"single_a5", "single_4x6", "b6_on_a5"}` so the Desktop and Android options
match the shared Word reflow implementation.

- [ ] **Step 4: Add horizontal compatibility and warning tests**

```python
def test_convert_docx_horizontal_emits_no_tb_rl(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    output = tmp_path / "horizontal.docx"
    document = Document()
    document.add_paragraph("橫排正文")
    document.save(source)
    convert_docx(
        source,
        output,
        LayoutSettings(
            imposition_mode="single_a5",
            writing_mode="horizontal",
            binding_direction="left",
        ),
    )
    with ZipFile(output) as archive:
        assert b'<w:textDirection w:val="tbRl"' not in archive.read("word/document.xml")


def test_vertical_docx_warns_about_non_word_viewers(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    output = tmp_path / "vertical.docx"
    document = Document()
    document.add_paragraph("直排正文")
    document.save(source)
    result = convert_docx(
        source,
        output,
        LayoutSettings(
            imposition_mode="single_a5",
            writing_mode="taiwan_vertical",
            binding_direction="right",
        ),
    )
    assert any("Microsoft Word" in warning for warning in result.warnings)
```

- [ ] **Step 5: Run all Word reflow tests**

Run: `python -m pytest python-tests/core/test_word_reflow.py -q`

Expected: PASS with existing A5/4×6 behavior and object fitting unchanged.

- [ ] **Step 6: Commit Word reflow support**

```bash
git add python/src/epub_a4_word/word_reflow.py python-tests/core/test_word_reflow.py
git commit -m "feat: reflow Word documents in native vertical mode"
```

---

### Task 6: Desktop direction selector and visual preview

**Files:**
- Modify: `python/src/epub_a4_word_desktop/conversion/models.py`
- Modify: `python/src/epub_a4_word_desktop/conversion/layout_preview.py`
- Modify: `python/src/epub_a4_word_desktop/pages/converter_page.py`
- Test: `desktop/tests/test_conversion_controller.py`
- Test: `desktop/tests/test_converter_page.py`
- Test: `desktop/tests/test_layout_preview.py`

**Interfaces:**
- Adds: `ConversionRequest.writing_mode = "taiwan_vertical"`
- Adds: `ConversionRequest.binding_direction = "right"`
- Desktop selector data values: `("taiwan_vertical", "right")` and `("horizontal", "left")`
- Preview exposes: `reading_direction_message`

- [ ] **Step 1: Write failing Desktop request and default tests**

```python
def test_request_defaults_to_taiwan_vertical_right_binding(tmp_path: Path) -> None:
    request = make_request(tmp_path)
    assert request.writing_mode == "taiwan_vertical"
    assert request.binding_direction == "right"
    settings = request.to_layout_settings()
    assert (settings.writing_mode, settings.binding_direction) == (
        "taiwan_vertical",
        "right",
    )


def test_converter_direction_selector_builds_horizontal_left_request(qtbot, tmp_path) -> None:
    page = ConverterPage(FakeController())
    qtbot.addWidget(page)
    page.direction_combo.setCurrentIndex(
        page.direction_combo.findData(("horizontal", "left"))
    )
    request = page._preview_request("single_a5")
    assert (request.writing_mode, request.binding_direction) == ("horizontal", "left")
```

- [ ] **Step 2: Run Desktop focused tests and verify failure**

Run: `python -m pytest desktop/tests/test_conversion_controller.py desktop/tests/test_converter_page.py -k "direction or vertical_right" -q`

Expected: FAIL because request fields and selector do not exist.

- [ ] **Step 3: Add request validation and selector**

Add a `QComboBox` named `conversion-writing-direction` with:

```python
_DIRECTION_PRESETS = (
    ("台灣直排（右裝訂）", ("taiwan_vertical", "right")),
    ("橫排（左裝訂）", ("horizontal", "left")),
)
```

Insert it after output mode. Map its tuple into `_preview_request` and
`_build_request`. Disable it while conversion runs. Validate each value
against the shared valid sets and pass them through `to_layout_settings`.

- [ ] **Step 4: Draw an explicit right-to-left preview cue**

In `LayoutPreview.paintEvent`, when vertical:

- draw three short vertical sample columns from right to left;
- draw a downward arrow in the rightmost column;
- draw a left-pointing arrow across the columns;
- render `右裝訂` below the page.

Expose:

```python
@property
def reading_direction_message(self) -> str:
    return (
        "直排：由上往下、欄位由右往左；右裝訂"
        if self._settings.writing_mode == "taiwan_vertical"
        else "橫排：由左往右；左裝訂"
    )
```

Include this text in the tooltip so the behavior is testable without pixel
comparison.

- [ ] **Step 5: Add preview and page-number-switch assertions**

```python
def test_vertical_preview_reports_right_to_left_reading(qtbot) -> None:
    preview = LayoutPreview()
    qtbot.addWidget(preview)
    preview.set_settings(
        LayoutSettings(
            writing_mode="taiwan_vertical",
            binding_direction="right",
        )
    )
    assert preview.reading_direction_message == "直排：由上往下、欄位由右往左；右裝訂"
    assert "右裝訂" in preview.toolTip()
```

Extend `test_start_builds_request_from_form` to assert that unchecking the
single existing `page_numbers` checkbox yields `page_numbers is False` while
the selected direction remains unchanged.

- [ ] **Step 6: Run Desktop tests**

Run: `python -m pytest desktop/tests/test_conversion_controller.py desktop/tests/test_converter_page.py desktop/tests/test_layout_preview.py -q`

Expected: PASS.

- [ ] **Step 7: Commit Desktop controls**

```bash
git add python/src/epub_a4_word_desktop/conversion/models.py python/src/epub_a4_word_desktop/conversion/layout_preview.py python/src/epub_a4_word_desktop/pages/converter_page.py desktop/tests/test_conversion_controller.py desktop/tests/test_converter_page.py desktop/tests/test_layout_preview.py
git commit -m "feat: add Desktop vertical layout selector"
```

---

### Task 7: Android direction selector, wire contract, and preview

**Files:**
- Modify: `app/src/main/java/tw/daniel/epubword/model/ConversionModels.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/MainActivity.kt`
- Modify: `app/src/main/python/android_bridge.py`
- Test: `app/src/test/java/tw/daniel/epubword/model/ConversionModelsTest.kt`
- Test: `app/src/test/java/tw/daniel/epubword/ui/AppRouteStateTest.kt`
- Test: `python-tests/test_android_bridge.py`

**Interfaces:**
- Produces Kotlin enum: `WritingPreset(writingMode, bindingDirection, label)`
- Adds: `ConversionOptions.writingPreset = WritingPreset.TAIWAN_VERTICAL`
- Adds: `ConversionViewModel.setWritingPreset(preset)`
- Adds bridge allow-list entries: `writing_mode`, `binding_direction`

- [ ] **Step 1: Write failing Kotlin JSON contract tests**

```kotlin
@Test
fun defaultsToTaiwanVerticalRightBinding() {
    val options = ConversionOptions()
    assertEquals(WritingPreset.TAIWAN_VERTICAL, options.writingPreset)
    val json = JSONObject(options.toJson())
    assertEquals("taiwan_vertical", json.getString("writing_mode"))
    assertEquals("right", json.getString("binding_direction"))
}

@Test
fun horizontalPresetSendsHorizontalLeftPair() {
    val json = JSONObject(
        ConversionOptions(writingPreset = WritingPreset.HORIZONTAL).toJson(),
    )
    assertEquals("horizontal", json.getString("writing_mode"))
    assertEquals("left", json.getString("binding_direction"))
}
```

- [ ] **Step 2: Run the focused Android model tests and verify failure**

Run: `gradle --no-daemon :app:testDebugUnitTest --tests "tw.daniel.epubword.model.ConversionModelsTest"`

Expected: FAIL because `WritingPreset` does not exist.

- [ ] **Step 3: Add the paired Kotlin preset and JSON fields**

```kotlin
enum class WritingPreset(
    val writingMode: String,
    val bindingDirection: String,
    val label: String,
) {
    TAIWAN_VERTICAL("taiwan_vertical", "right", "台灣直排（右裝訂）"),
    HORIZONTAL("horizontal", "left", "橫排（左裝訂）"),
}
```

Add it to `ConversionOptions`, emit both wire fields in `toJson`, and add
`setWritingPreset` to the ViewModel.

- [ ] **Step 4: Add bridge allow-list and validation coverage**

```python
def test_android_bridge_accepts_vertical_direction_pair(monkeypatch, tmp_path) -> None:
    source = tmp_path / "book.epub"
    output = tmp_path / "book.docx"
    source.write_bytes(b"fixture")
    captured = {}

    def fake_convert(input_path, output_path, settings, progress, *, content_only=True):
        captured["settings"] = settings
        output.write_bytes(b"docx")
        return SimpleNamespace(
            output_path=output,
            title="",
            author="",
            mini_page_count=1,
            a4_page_count=1,
            image_count=0,
            warnings=(),
            imposition_mode=settings.imposition_mode,
            paper_sheet_count=1,
            signature_count=0,
            padded_mini_page_count=1,
            source_format="epub",
        )

    monkeypatch.setattr(android_bridge, "convert_input", fake_convert)
    android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps(
            {
                "writing_mode": "taiwan_vertical",
                "binding_direction": "right",
            }
        ),
    )
    assert captured["settings"].writing_mode == "taiwan_vertical"
    assert captured["settings"].binding_direction == "right"


@pytest.mark.parametrize(
    "options",
    [
        {"writing_mode": "diagonal"},
        {"binding_direction": "middle"},
    ],
)
def test_android_bridge_rejects_invalid_direction_values(options, tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        android_bridge._settings_for("epub", options)
```

Add both names to `_SETTING_FIELDS`; let shared `resolve_layout` validation
run before conversion so Python and Android return the same explicit error.

- [ ] **Step 5: Add Compose selector and reading-direction preview**

Add `onWritingPreset: (WritingPreset) -> Unit` through `ConverterScreen`,
`AppRoot`, and `MainActivity`. In Step 3 of the converter, render two
full-width `FilterChip`s and a small preview card:

```kotlin
Text(
    if (state.options.writingPreset == WritingPreset.TAIWAN_VERTICAL) {
        "由上往下，欄位由右往左 · 右裝訂"
    } else {
        "由左往右 · 左裝訂"
    },
    modifier = Modifier.testTag("reading-direction-preview"),
)
```

Keep the existing `SettingCheck("顯示頁碼", ...)` as the only page-number
control. Add the Microsoft Word compatibility note only for vertical mode.

- [ ] **Step 6: Add state/UI callback coverage**

Extend `AppRouteStateTest` or add a focused Compose unit test to verify:

- initial options are `TAIWAN_VERTICAL`;
- selecting `HORIZONTAL` updates the state;
- the preview semantics contains `左裝訂`;
- toggling `pageNumbers` to false does not alter the writing preset.

- [ ] **Step 7: Run bridge and Android tests**

Run: `python -m pytest python-tests/test_android_bridge.py -q`

Run: `gradle --no-daemon :app:testDebugUnitTest`

Expected: PASS.

- [ ] **Step 8: Commit Android controls**

```bash
git add app/src/main/java/tw/daniel/epubword/model/ConversionModels.kt app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt app/src/main/java/tw/daniel/epubword/MainActivity.kt app/src/main/python/android_bridge.py app/src/test/java/tw/daniel/epubword/model/ConversionModelsTest.kt app/src/test/java/tw/daniel/epubword/ui/AppRouteStateTest.kt python-tests/test_android_bridge.py
git commit -m "feat: add Android vertical layout selector"
```

---

### Task 8: Cross-path vertical conversion regression

**Files:**
- Modify: `python-tests/core/test_integration.py`
- Modify: `python-tests/test_android_bridge.py`
- Create: `python-tests/fixtures/vertical_mixed.epub`

**Interfaces:**
- Consumes all interfaces from Tasks 1–7.
- Produces a real packaged DOCX acceptance fixture covering CJK, English, digits, headings, images, page breaks, page numbers, and right-bound imposition.

- [ ] **Step 1: Add the minimal mixed vertical EPUB fixture**

Create a valid EPUB containing:

- title and author metadata;
- one heading `第一章`;
- body `中文 English 2026` repeated enough to make multiple columns;
- a manual page break;
- one portrait PNG followed by body text.

Use the same ZIP construction pattern already present in
`python-tests/test_android_bridge.py`; store `mimetype` uncompressed.

- [ ] **Step 2: Write the failing end-to-end regression**

```python
def test_vertical_epub_end_to_end_is_right_bound_and_reopenable(tmp_path: Path) -> None:
    output = tmp_path / "vertical.docx"
    result = convert_epub(
        FIXTURES / "vertical_mixed.epub",
        output,
        LayoutSettings(
            imposition_mode="signature16",
            writing_mode="taiwan_vertical",
            binding_direction="right",
            page_numbers=True,
        ),
    )
    reopened = Document(output)
    text = "\n".join(cell.text for table in reopened.tables for row in table.rows for cell in row.cells)
    assert "中文 English 2026" in text
    assert len(reopened.inline_shapes) == 1
    assert result.mini_page_count >= 2
    with ZipFile(output) as archive:
        xml = archive.read("word/document.xml")
        assert b'<w:textDirection w:val="tbRl"' in xml
```

- [ ] **Step 3: Run the regression and repair only uncovered integration seams**

Run: `python -m pytest python-tests/core/test_integration.py python-tests/test_android_bridge.py -q`

Expected: PASS. If a failure exposes a missing settings pass-through, update
the narrow caller and add its assertion to the same test before continuing.

- [ ] **Step 4: Run the complete Python and Desktop suites**

Run: `python -m pytest python-tests desktop/tests -q`

Expected: PASS.

- [ ] **Step 5: Commit vertical integration coverage**

```bash
git add python-tests/core/test_integration.py python-tests/test_android_bridge.py python-tests/fixtures/vertical_mixed.epub
git commit -m "test: cover vertical conversion end to end"
```
