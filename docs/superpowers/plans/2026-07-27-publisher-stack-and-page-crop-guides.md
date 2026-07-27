# Publisher Stack and Page Crop Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成出版社資訊自動堆疊與譯者欄位，並讓 B6 正文固定置於 A5 右下角、所有正文輸出模式使用統一且正確的裁切／折線規劃。

**Architecture:** 封面部分以共享 `publisher_info_layout` 模組產生可序列化的文字框幾何，模板、Pillow 渲染與 Qt 畫布只消費同一份結果；群組操作由桌面控制器依 `group_id` 展開成原子專案更新。正文部分新增獨立 `page_placement` 核心，輸出紙張、內容矩形與 `CropGuide`，DOCX 寫入器不再自行推算裁切線。

**Tech Stack:** Python 3.13、dataclasses、Pillow 11、python-docx 1.1、PySide6 6.11、pytest／pytest-qt、GitHub Actions。

## Global Constraints

- 保留封面專案 `schema_version=1`，舊 JSON 缺少 `translator` 時視為空字串。
- 不下載、生成、打包或分享任何字型檔；只偵測使用者電腦已安裝字型。
- `DFPYuanW5-GB` 與 `DFPYuanW3-GB` 必須分別位於出版社標題與細節字體候選首位。
- B6-on-A5 固定為 A5 `148 × 210 mm`、B6 `128 × 182 mm`、內容矩形 `(20, 28, 128, 182)`。
- B6-on-A5 裁切線固定為 `(0,28)→(20,28)` 與 `(20,0)→(20,28)`，線寬 `0.35 pt`，不得伸入 B6 成品區。
- `single_a5` 與 `single_4x6` 成品等於紙張時不建立內部裁切線。
- `four_up` 的內部分隔線角色為 `crop`；`signature16` 的中心折線角色為 `fold`。
- 現有「正常／裁切線」與 `cut_guides` 設定只控制線條顯示，不改變內容位置。
- 本計畫不修改 Android 產品介面；Android 僅做共享核心相容性建置。

---

### Task 1: 譯者欄位與 schema-v1 相容性

**Files:**
- Modify: `python/src/epub_a4_word/cover/models.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Test: `python-tests/cover/test_translator_metadata.py`
- Test: `desktop/tests/test_cover_setup_translator.py`

**Interfaces:**
- Produces: `CoverMetadata.translator: str = ""`
- Produces: `CoverSetupValues.translator: str = ""`
- Consumes: `settings_json["translator"]` as an optional string in `service.new_project`

- [ ] **Step 1: Write the failing shared tests**

```python
from dataclasses import replace
import json

from epub_a4_word.cover.models import CoverMetadata
from epub_a4_word.cover.project_io import dumps_project, loads_project


def test_translator_round_trips_in_schema_v1(make_cover_project):
    project = make_cover_project(metadata=CoverMetadata(title="書名", translator="李彥樺"))
    loaded = loads_project(dumps_project(project))
    assert loaded.schema_version == 1
    assert loaded.metadata.translator == "李彥樺"


def test_old_schema_v1_without_translator_loads_empty(make_cover_project):
    project = make_cover_project(metadata=CoverMetadata(title="書名"))
    raw = json.loads(dumps_project(project))
    raw["metadata"].pop("translator", None)
    loaded = loads_project(json.dumps(raw, ensure_ascii=False))
    assert loaded.metadata.translator == ""
```

- [ ] **Step 2: Run shared test and verify RED**

Run: `python -m pytest python-tests/cover/test_translator_metadata.py -q`
Expected: FAIL because `CoverMetadata` does not accept `translator`.

- [ ] **Step 3: Add the model and serializer support**

```python
@dataclass(frozen=True)
class CoverMetadata:
    ...
    publication_place: str = ""
    translator: str = ""
    isbn_addon: str = ""
```

Add `translator` to `_validate_metadata`, `_metadata_from_dict.allowed`, and the `CoverMetadata(...)` reconstruction using `data.get("translator", "")`.

- [ ] **Step 4: Run shared test and verify GREEN**

Run: `python -m pytest python-tests/cover/test_translator_metadata.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing desktop setup test**

```python
def test_setup_values_include_trimmed_translator(qtbot, tmp_path):
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    panel.set_source(tmp_path / "book.epub", page_count=160, confirmed=True)
    panel.translator_edit.setText("  李彥樺  ")
    values = panel.values()
    assert values.translator == "李彥樺"
    assert values.settings(tmp_path)["translator"] == "李彥樺"
```

- [ ] **Step 6: Run desktop test and verify RED**

Run: `python -m pytest desktop/tests/test_cover_setup_translator.py -q`
Expected: FAIL because `translator_edit` and `CoverSetupValues.translator` do not exist.

- [ ] **Step 7: Add the translator input and service boundary**

Add `translator_edit = QLineEdit`, the form row `譯者`, `CoverSetupValues.translator`, and `"translator"` in `settings()`. Add `translator` to `service._ALLOWED_SETTINGS`; in `new_project`, replace inspected metadata with a trimmed setting when present:

```python
translator = str(settings.get("translator", "")).strip()
metadata = replace(
    inspection.metadata,
    translator=translator or inspection.metadata.translator,
    page_count_is_estimate=estimated,
)
```

- [ ] **Step 8: Run both test files and commit**

Run: `python -m pytest python-tests/cover/test_translator_metadata.py desktop/tests/test_cover_setup_translator.py -q`
Expected: PASS.

Commit: `feat: add translator metadata support`

---

### Task 2: 共享出版社資訊版面與字體優先順序

**Files:**
- Create: `python/src/epub_a4_word/cover/publisher_info_layout.py`
- Modify: `python/src/epub_a4_word/cover/typography.py`
- Modify: `python/src/epub_a4_word/cover/fonts.py`
- Test: `python-tests/cover/test_publisher_info_layout.py`

**Interfaces:**
- Produces: `PublisherInfoLine(text: str, role: Literal["heading", "details"])`
- Produces: `PublisherInfoLayout(heading_rect, details_rect, heading_font_pt, details_font_pt, detail_lines, warnings)`
- Produces: `build_publisher_info_lines(metadata: CoverMetadata) -> tuple[PublisherInfoLine, ...]`
- Produces: `layout_publisher_info(..., measure: TextMeasure | None = None) -> PublisherInfoLayout`

- [ ] **Step 1: Write failing line-construction and geometry tests**

```python
def test_publisher_lines_skip_empty_values_and_do_not_duplicate_translator_prefix():
    metadata = CoverMetadata(
        publisher="台灣角川",
        price="NT$110/HK$35",
        publication_place="",
        translator="譯者：李彥樺",
    )
    lines = build_publisher_info_lines(metadata)
    assert [line.text for line in lines] == [
        "台灣角川",
        "定價：NT$110/HK$35",
        "譯者：李彥樺",
    ]


def test_missing_heading_starts_details_at_stack_top():
    layout = layout_publisher_info(
        metadata=CoverMetadata(price="NT$110"),
        x_mm=80.0,
        y_mm=10.0,
        max_width_mm=50.0,
        max_height_mm=30.0,
        measure=fixed_measure,
    )
    assert layout.heading_rect is None
    assert layout.details_rect.y_mm == 10.0


def test_missing_middle_line_compacts_following_lines():
    layout = layout_publisher_info(
        metadata=CoverMetadata(publisher="台灣角川", translator="李彥樺"),
        x_mm=80.0,
        y_mm=10.0,
        max_width_mm=50.0,
        max_height_mm=30.0,
        measure=fixed_measure,
    )
    assert layout.detail_lines == ("譯者：李彥樺",)
    assert layout.details_rect.y_mm == pytest.approx(layout.heading_rect.bottom_mm + 1.0)
```

- [ ] **Step 2: Run layout test and verify RED**

Run: `python -m pytest python-tests/cover/test_publisher_info_layout.py -q`
Expected: import failure because `publisher_info_layout` does not exist.

- [ ] **Step 3: Implement the pure layout algorithm**

Use `RectMm` and a small measurement protocol:

```python
@dataclass(frozen=True)
class TextMeasure:
    width_mm: float
    line_height_mm: float

MeasureText = Callable[[str, str, float], TextMeasure]
```

Rules implemented exactly: trim values, omit empty rows, normalize `譯者：`, heading gap `1.0 mm`, details baseline spacing `1.12 × line_height`, shrink to `5.5 pt` before wrapping, and return overflow warnings instead of silently clipping.

- [ ] **Step 4: Run layout tests and verify GREEN**

Run: `python -m pytest python-tests/cover/test_publisher_info_layout.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing font-order test**

```python
def test_dfp_yuan_gb_names_are_first_candidates():
    assert font_candidates("publisher_heading")[:2] == (
        "DFPYuanW5-GB",
        "DFPYuanW5",
    )
    assert font_candidates("publisher_details")[:2] == (
        "DFPYuanW3-GB",
        "DFPYuanW3",
    )
```

- [ ] **Step 6: Run the font test and verify RED**

Run: `python -m pytest python-tests/cover/test_publisher_info_layout.py::test_dfp_yuan_gb_names_are_first_candidates -q`
Expected: FAIL because the GB PostScript names are absent or not first.

- [ ] **Step 7: Update exact-match candidate and filename aliases**

Add the candidate order from the design and aliases for normalized names `dfpyuanw5gb`, `dfpyuanw3gb`, `dfpyuanw5`, and `dfpyuanw3`. Keep family matching case-insensitive and deterministic.

- [ ] **Step 8: Run tests and commit**

Run: `python -m pytest python-tests/cover/test_publisher_info_layout.py -q`
Expected: PASS.

Commit: `feat: add shared publisher info layout`

---

### Task 3: 模板與正式渲染共用資訊群結果

**Files:**
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word/cover/docx_export.py`
- Test: `python-tests/cover/test_publisher_back_template.py`
- Test: `python-tests/cover/test_publisher_info_rendering.py`

**Interfaces:**
- Consumes: `layout_publisher_info(...) -> PublisherInfoLayout`
- Produces element content keys: `group_id="publisher-info-stack"`, `layout_role`, `font_role`, `line_spacing`, `vertical_align="top"`

- [ ] **Step 1: Write failing template tests**

```python
def test_publisher_template_uses_shared_compact_stack(make_cover_project):
    project = make_cover_project(
        metadata=CoverMetadata(
            publisher="台灣角川",
            price="NT$110/HK$35",
            translator="李彥樺",
        )
    )
    result = apply_template(project, "publisher_back_matter")
    heading = result.elements_by_id["back-publisher-heading"]
    details = result.elements_by_id["back-publisher-details"]
    assert heading.content["group_id"] == "publisher-info-stack"
    assert details.content["group_id"] == "publisher-info-stack"
    assert heading.transform.x_mm == details.transform.x_mm
    assert details.content["text"].splitlines()[-1] == "譯者：李彥樺"
    assert details.transform.y_mm == pytest.approx(
        heading.transform.y_mm + heading.transform.height_mm + 1.0
    )
```

- [ ] **Step 2: Run template test and verify RED**

Run: `python -m pytest python-tests/cover/test_publisher_back_template.py -q`
Expected: FAIL because the template still uses fixed rectangles and has no translator row.

- [ ] **Step 3: Replace fixed heading/details geometry with shared layout output**

The template computes one stack start and safe width, calls `layout_publisher_info`, and creates only non-empty members. Preserve existing IDs for compatibility. Add layout warnings to `project.background["warnings"]` without duplicating identical messages.

- [ ] **Step 4: Run template tests and verify GREEN**

Run: `python -m pytest python-tests/cover/test_publisher_back_template.py -q`
Expected: PASS.

- [ ] **Step 5: Write failing Pillow/DOCX tests**

Assert that heading/details are top-aligned, use their separate font roles and font sizes, and that empty rows do not create blank paragraphs or fixed-height spacer blocks.

- [ ] **Step 6: Run rendering tests and verify RED**

Run: `python -m pytest python-tests/cover/test_publisher_info_rendering.py -q`
Expected: FAIL because render/export does not consume line spacing and compact stack metadata.

- [ ] **Step 7: Make renderers consume stored layout metadata**

Pillow and DOCX must use `vertical_align="top"`, stored `font_size_pt`, and stored `line_spacing`. They must not recalculate stack positions independently.

- [ ] **Step 8: Run cover tests and commit**

Run: `python -m pytest python-tests/cover -q`
Expected: PASS.

Commit: `feat: render compact publisher info stack`

---

### Task 4: 桌面版出版社資訊群組操作

**Files:**
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Modify: `python/src/epub_a4_word_desktop/cover/canvas.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `desktop/tests/test_publisher_info_group.py`

**Interfaces:**
- Produces: `CoverController.group_members(element_id: str) -> tuple[CoverElement, ...]`
- Produces: `CoverController.update_group_transform(element_id: str, transform: Mapping[str, float]) -> None`
- Produces: `CoverController.remove_element` and visibility changes expanding to all same-`group_id` members

- [ ] **Step 1: Write failing controller group tests**

Test that moving heading by `(dx, dy)` moves details by the same delta; deleting or hiding either member affects both; unrelated elements are unchanged.

- [ ] **Step 2: Run controller tests and verify RED**

Run: `python -m pytest desktop/tests/test_publisher_info_group.py -q`
Expected: FAIL because operations target only one element.

- [ ] **Step 3: Implement atomic group expansion in the controller**

Read `group_id` from selected element content. Build one replacement `CoverProject` containing all member changes and push one undo command. Scaling applies the same ratio to relative positions, widths, heights, font sizes, and `line_spacing`.

- [ ] **Step 4: Run controller tests and verify GREEN**

Run: `python -m pytest desktop/tests/test_publisher_info_group.py -q`
Expected: PASS.

- [ ] **Step 5: Write failing canvas selection test**

Selecting either stack member must select both scene items and emit the originally clicked ID for the inspector; the union of `sceneBoundingRect()` values is the displayed group bounds.

- [ ] **Step 6: Run canvas test and verify RED**

Run: `python -m pytest desktop/tests/test_publisher_info_group.py::test_canvas_selects_entire_publisher_group -q`
Expected: FAIL because selection currently selects one item.

- [ ] **Step 7: Synchronize group selection and transform routing**

`CoverCanvas.set_project` stores `group_id -> item ids`. `_selection_changed` expands a newly selected group while blocking recursive scene signals. Transform commits from a group member call `update_group_transform` through `CoverPage`; non-group elements keep the existing path.

- [ ] **Step 8: Run desktop tests and commit**

Run: `python -m pytest desktop/tests -q`
Expected: PASS.

Commit: `feat: edit publisher info as a group`

---

### Task 5: 統一正文 PagePlacement 與 CropGuide

**Files:**
- Create: `python/src/epub_a4_word/page_placement.py`
- Modify: `python/src/epub_a4_word/pagination.py`
- Test: `python-tests/test_page_placement.py`

**Interfaces:**
- Produces:

```python
GuideRole = Literal["crop", "fold"]

@dataclass(frozen=True)
class CropGuide:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    role: GuideRole = "crop"

@dataclass(frozen=True)
class PagePlacement:
    paper_width_mm: float
    paper_height_mm: float
    content_x_mm: float
    content_y_mm: float
    content_width_mm: float
    content_height_mm: float
    guides: tuple[CropGuide, ...]
```

- Produces: `build_page_placement(settings: LayoutSettings) -> PagePlacement`

- [ ] **Step 1: Write the failing B6 geometry test**

```python
def test_b6_on_a5_uses_bottom_right_trim_and_l_guides():
    settings = resolve_layout(LayoutSettings(
        imposition_mode="b6_on_a5",
        output_mark_mode="crop_marks",
    ))
    placement = build_page_placement(settings)
    assert (
        placement.content_x_mm,
        placement.content_y_mm,
        placement.content_width_mm,
        placement.content_height_mm,
    ) == pytest.approx((20.0, 28.0, 128.0, 182.0))
    assert placement.guides == (
        CropGuide(0.0, 28.0, 20.0, 28.0, "crop"),
        CropGuide(20.0, 0.0, 20.0, 28.0, "crop"),
    )
```

- [ ] **Step 2: Run placement test and verify RED**

Run: `python -m pytest python-tests/test_page_placement.py -q`
Expected: import failure because `page_placement` does not exist; current B6 margins are symmetric.

- [ ] **Step 3: Implement B6 placement and change resolved margins**

For `b6_on_a5`, resolve margins to `left=2.0 cm`, `right=0.0 cm`, `top=2.8 cm`, `bottom=0.0 cm`; keep cell size `12.8 × 18.2 cm`. `build_page_placement` converts the resolved values to millimetres and creates the exact two guides only when `output_mark_mode == "crop_marks"`.

- [ ] **Step 4: Run B6 tests and verify GREEN**

Run: `python -m pytest python-tests/test_page_placement.py -q`
Expected: PASS for B6 tests.

- [ ] **Step 5: Write the mode matrix tests**

```python
@pytest.mark.parametrize("mode", ["single_a5", "single_4x6"])
def test_single_sheet_modes_have_no_internal_guides(mode):
    settings = resolve_layout(LayoutSettings(imposition_mode=mode, output_mark_mode="crop_marks"))
    assert build_page_placement(settings).guides == ()


def test_four_up_uses_solid_crop_guides():
    placement = build_page_placement(resolve_layout(LayoutSettings(imposition_mode="four_up")))
    assert {guide.role for guide in placement.guides} == {"crop"}


def test_signature16_uses_fold_guides():
    placement = build_page_placement(resolve_layout(LayoutSettings(imposition_mode="signature16")))
    assert {guide.role for guide in placement.guides} == {"fold"}
```

- [ ] **Step 6: Run matrix and verify RED**

Run: `python -m pytest python-tests/test_page_placement.py -q`
Expected: FAIL because grid guides are not implemented.

- [ ] **Step 7: Add deterministic grid guide construction**

Create one vertical guide for each internal column boundary and one horizontal guide for each internal row boundary. Use the content grid rectangle, deduplicate identical segments, assign role `crop` for `four_up` and `fold` for `signature16`, and suppress all guides when the corresponding setting is off.

- [ ] **Step 8: Run placement tests and commit**

Run: `python -m pytest python-tests/test_page_placement.py -q`
Expected: PASS.

Commit: `feat: add unified page placement guides`

---

### Task 6: DOCX 右下角放置與全模式線條渲染

**Files:**
- Modify: `python/src/epub_a4_word/crop_marks.py`
- Modify: `python/src/epub_a4_word/docx_writer.py`
- Test: `python-tests/test_docx_page_guides.py`

**Interfaces:**
- Consumes: `PagePlacement.guides`
- Produces: `add_page_guides(section, guides: Sequence[CropGuide], *, stroke_pt: float = 0.35) -> None`

- [ ] **Step 1: Write failing DOCX XML tests for B6**

Generate a one-page B6-on-A5 DOCX, unzip it, and assert:
- section margins are left `2.0 cm`, right `0`, top `2.8 cm`, bottom `0`;
- header VML contains exactly two lines;
- their point coordinates equal the two specified L segments;
- no coordinate extends into `x>20 mm and y>=28 mm`.

- [ ] **Step 2: Run B6 DOCX test and verify RED**

Run: `python -m pytest python-tests/test_docx_page_guides.py::test_b6_docx_uses_bottom_right_content_and_l_guides -q`
Expected: FAIL because the current writer uses symmetric margins and eight generic crop marks.

- [ ] **Step 3: Generalize crop mark rendering**

Replace frame-based eight-segment generation with `add_page_guides`. Emit one VML line per `CropGuide`; use `strokeweight="0.35pt"`; use solid for `crop` and dash style for `fold`. Keep a compatibility wrapper only if existing cover code imports `add_crop_marks`.

- [ ] **Step 4: Make DOCX writer consume PagePlacement**

Call `build_page_placement(settings)` once. Set section margins from the placement/resolved settings, render placement guides in the header, and disable `_set_table_borders` as an independent guide source so lines are not duplicated or thickened.

- [ ] **Step 5: Run B6 DOCX test and verify GREEN**

Run: `python -m pytest python-tests/test_docx_page_guides.py::test_b6_docx_uses_bottom_right_content_and_l_guides -q`
Expected: PASS.

- [ ] **Step 6: Write failing all-mode XML matrix tests**

Verify:
- `normal` mode creates no header guides but retains B6 margins;
- `single_a5` and `single_4x6` create no internal lines;
- `four_up` creates one solid vertical and one solid horizontal divider;
- `signature16` creates one dashed vertical and one dashed horizontal fold line;
- no duplicate table border lines remain.

- [ ] **Step 7: Run matrix and verify RED, then implement minimal fixes**

Run: `python -m pytest python-tests/test_docx_page_guides.py -q`
Expected before fixes: FAIL on missing mode-specific lines or duplicate table borders.

- [ ] **Step 8: Run DOCX tests and commit**

Run: `python -m pytest python-tests/test_docx_page_guides.py -q`
Expected: PASS.

Commit: `fix: place B6 at A5 bottom right with page guides`

---

### Task 7: 全量回歸、視覺證據與跨平台建置

**Files:**
- Modify: `.github/workflows/desktop-tests.yml` only if the existing workflow does not already execute the new tests
- Create temporarily then delete: `.github/workflows/manual-layout-regression.yml` only when a targeted CI run is required
- Update: PR #13 description after verified results

**Interfaces:** none.

- [ ] **Step 1: Run targeted shared suites**

Run:

```bash
python -m pytest \
  python-tests/cover/test_translator_metadata.py \
  python-tests/cover/test_publisher_info_layout.py \
  python-tests/cover/test_publisher_back_template.py \
  python-tests/cover/test_publisher_info_rendering.py \
  python-tests/test_page_placement.py \
  python-tests/test_docx_page_guides.py -q
```

Expected: PASS.

- [ ] **Step 2: Run complete shared and desktop suites**

Run:

```bash
python -m pytest python-tests -q
QT_QPA_PLATFORM=offscreen python -m pytest desktop/tests -q
python -m compileall -q python/src
```

Expected: all PASS, no unexpected warnings.

- [ ] **Step 3: Produce non-generated visual regression evidence**

Render one publisher-back preview and one B6-on-A5 DOCX/PDF preview from real test fixtures. Inspect that text lines are left-aligned and compact, the B6 content touches the A5 right/bottom edges, and only the two L guides appear in the upper-left waste area.

- [ ] **Step 4: Run CI matrix**

Confirm Desktop PySide6 on Ubuntu, Windows and macOS; Windows portable EXE; Android debug APK shared-core compatibility.

- [ ] **Step 5: Remove any temporary workflow and rerun affected checks**

Expected: the final diff contains no one-off workflow.

- [ ] **Step 6: Update PR status without merging**

Keep PR #13 as draft until the visual evidence and all workflows pass. Update its body with exact final head SHA, pass counts, known limitations, and confirm Android UI was not modified.

- [ ] **Step 7: Commit final documentation**

Commit: `docs: record publisher and crop guide verification`
