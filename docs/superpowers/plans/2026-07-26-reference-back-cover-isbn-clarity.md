# Reference Back Cover and ISBN Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the publisher back-cover template match the supplied reference layout and replace unexplained ISBN lists with one recommended ISBN-13 plus clearly labelled same-edition metadata.

**Architecture:** Keep the existing schema-v1 project and `SearchCandidate` serialization. Encode the reference layout as deterministic safe-area ratios in `templates.py`, make publisher-logo insertion use `contain`, and isolate ISBN presentation in pure helper functions consumed by the PySide6 candidate cards and selection summary.

**Tech Stack:** Python 3.13, dataclasses, PySide6, Pillow, pytest, pytest-qt.

## Global Constraints

- Do not generate, download, or bundle any publisher logo image.
- Treat the user-supplied second screenshot as the fixed default layout reference.
- Keep all generated back-cover elements movable, resizable, hideable, and deletable.
- Show one recommended ISBN-13; ISBN-10 is only a labelled same-edition corresponding code.
- Do not list unexplained resolved ISBN values in the search summary.
- Do not change the Android product code or add search providers.

---

### Task 1: Encode the reference back-cover geometry

**Files:**
- Modify: `python-tests/cover/test_publisher_back_template.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`

**Interfaces:**
- Consumes: `calculate_layout(project) -> CoverLayout` and `CoverLayout.back_safe_rect`.
- Produces: deterministic `back-isbn-label`, `back-isbn-code`, `back-publisher-info`, and `background["publisher_logo_slot"]` rectangles.

- [ ] **Step 1: Write failing geometry assertions**

Add a test that normalizes every generated rectangle against `layout.back_safe_rect`:

```python
def _relative(rect, safe):
    return (
        (rect.x_mm - safe.x_mm) / safe.width_mm,
        (rect.y_mm - safe.y_mm) / safe.height_mm,
        rect.width_mm / safe.width_mm,
        rect.height_mm / safe.height_mm,
    )


def test_publisher_template_matches_reference_layout(sample_project):
    project = replace(
        sample_project(),
        metadata=replace(
            sample_project().metadata,
            isbn="9780306406157",
            publisher="台灣角川",
            price="定價：NT$110",
            publication_place="臺灣出版",
        ),
    )
    result = apply_template(project, "publisher_back_matter")
    safe = calculate_layout(result).back_safe_rect

    assert _relative(result.elements_by_id["back-isbn-label"].transform, safe) == pytest.approx(
        (0.10, 0.06, 0.36, 0.035), abs=0.01
    )
    assert _relative(result.elements_by_id["back-isbn-code"].transform, safe) == pytest.approx(
        (0.10, 0.105, 0.36, 0.105), abs=0.015
    )
    assert _relative(result.elements_by_id["back-publisher-info"].transform, safe) == pytest.approx(
        (0.48, 0.06, 0.30, 0.14), abs=0.015
    )
    slot = result.background["publisher_logo_slot"]
    assert (
        (slot["x_mm"] - safe.x_mm) / safe.width_mm,
        (slot["y_mm"] - safe.y_mm) / safe.height_mm,
        slot["width_mm"] / safe.width_mm,
        slot["height_mm"] / safe.height_mm,
    ) == pytest.approx((0.26, 0.34, 0.48, 0.36), abs=0.01)
```

Also assert that publisher information is left aligned and the cover label starts with `ISBN ` rather than presenting a second UI choice labelled `ISBN-13`.

- [ ] **Step 2: Run the focused template test**

Run: `python3.13 -m pytest python-tests/cover/test_publisher_back_template.py -q`

Expected: FAIL because the current ISBN/barcode block is 55% wide, the logo slot is 58% wide, and publisher information is right aligned.

- [ ] **Step 3: Implement the reference ratios**

In `templates.py`, calculate all positions from `back_safe_rect`:

```python
label_rect = RectMm(
    safe.x_mm + safe.width_mm * 0.10,
    safe.y_mm + safe.height_mm * 0.06,
    safe.width_mm * 0.36,
    safe.height_mm * 0.035,
)
barcode_rect = RectMm(
    label_rect.x_mm,
    safe.y_mm + safe.height_mm * 0.105,
    safe.width_mm * 0.36,
    safe.height_mm * 0.105,
)
info_rect = RectMm(
    safe.x_mm + safe.width_mm * 0.48,
    safe.y_mm + safe.height_mm * 0.06,
    safe.width_mm * 0.30,
    safe.height_mm * 0.14,
)
```

Set the central logo slot to x/y/width/height fractions `0.26/0.34/0.48/0.36`, use `align="left"` for publisher information, and render the label as `ISBN {isbn}`.

- [ ] **Step 4: Re-run the focused template test**

Run: `python3.13 -m pytest python-tests/cover/test_publisher_back_template.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python-tests/cover/test_publisher_back_template.py python/src/epub_a4_word/cover/templates.py
git commit -m "fix: match publisher back cover reference layout"
```

### Task 2: Preserve the complete central logo with contain fitting

**Files:**
- Modify: `desktop/tests/test_publisher_workflow.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`

**Interfaces:**
- Consumes: `CoverController._target_rect(project, Region.BACK)` and `background["publisher_logo_slot"]`.
- Produces: publisher-logo image elements with `content["fit"] == "contain"`; all other added images retain `cover`.

- [ ] **Step 1: Write the failing controller test**

```python
def test_publisher_logo_image_uses_contain_without_cropping(tmp_path):
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    project = _publisher_project(tmp_path)
    controller.replace_project(dumps_project(project), clear_history=True)
    source = tmp_path / "publisher-logo.png"
    QPixmap(240, 120).save(str(source))

    element_id = controller.add_local_image(source, Region.BACK)

    updated = loads_project(controller.project_json)
    element = updated.elements_by_id[element_id]
    assert element.content["fit"] == "contain"
    assert element.transform == ElementTransform(**updated.background["publisher_logo_slot"])
```

Use explicit field comparison if `ElementTransform(**slot)` is not accepted by the dataclass constructor.

- [ ] **Step 2: Run the focused desktop test**

Run: `python3.13 -m pytest desktop/tests/test_publisher_workflow.py::test_publisher_logo_image_uses_contain_without_cropping -q`

Expected: FAIL because `_image_element` currently sets `fit` to `cover` for every image.

- [ ] **Step 3: Implement slot-aware fitting**

Add a pure predicate:

```python
@staticmethod
def _uses_publisher_logo_slot(project: CoverProject, region: Region) -> bool:
    return (
        region is Region.BACK
        and str(project.background.get("active_template", "")) == "publisher_back_matter"
        and isinstance(project.background.get("publisher_logo_slot"), Mapping)
    )
```

Use it in `_target_rect` and set `content["fit"]` to `"contain"` only for that slot. Preserve scale, offset, crop, movement, resize, and deletion behavior.

- [ ] **Step 4: Re-run publisher workflow tests**

Run: `python3.13 -m pytest desktop/tests/test_publisher_workflow.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add desktop/tests/test_publisher_workflow.py python/src/epub_a4_word_desktop/cover/controller.py
git commit -m "fix: contain publisher logo in reference slot"
```

### Task 3: Replace ISBN dumps with an explained recommendation

**Files:**
- Modify: `desktop/tests/test_publisher_workflow.py`
- Modify: `python/src/epub_a4_word_desktop/cover/search_panel.py`

**Interfaces:**
- Consumes: `SearchCandidate.isbn`, `SearchCandidate.isbns`, `publisher`, `language`, `title`, and `classification_reasons`.
- Produces: `candidate_isbn10(candidate) -> str`, `candidate_isbn_summary(candidate) -> str`, and `candidate_match_summary(candidate) -> str` for UI-only presentation.

- [ ] **Step 1: Replace the old ISBN-list test with failing clarity tests**

```python
def test_candidate_card_explains_recommended_and_corresponding_isbn(qtbot):
    candidate = SearchCandidate(
        provider="google_books",
        candidate_id="book",
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title="Example Volume 1",
        author="Author",
        isbn="9780306406157",
        isbns=("0306406152", "9780306406157"),
        publisher="Publisher",
        language="zh-TW",
        classification_reasons=("書名與卷數相符",),
        preview_url="https://example.test/preview.jpg",
        image_url="https://example.test/image.jpg",
        source_page="https://example.test/book",
    )
    card = CandidateCard(candidate, QNetworkAccessManager())
    qtbot.addWidget(card)

    text = card.isbn_label.text()
    assert "建議 ISBN-13：9780306406157" in text
    assert "對應 ISBN-10：0306406152（同一版本對應碼）" in text
    assert text.count("建議 ISBN-13") == 1
    assert "ISBN-10 0306406152\nISBN-13" not in text
    assert "出版社：Publisher" in card.edition_label.text()
    assert "語言：zh-TW" in card.edition_label.text()
    assert "判定：書名與卷數相符" in card.edition_label.text()
```

Add a second test where `isbns` contains an unrelated valid ISBN-10 and verify it is not labelled as the corresponding code. The matching rule is `isbn13_from_isbn10(value) == candidate.isbn`.

- [ ] **Step 2: Run the focused card tests**

Run: `python3.13 -m pytest desktop/tests/test_publisher_workflow.py -k candidate_card -q`

Expected: FAIL because cards currently print every ISBN without explanation and have no edition summary label.

- [ ] **Step 3: Implement pure presentation helpers and card labels**

Import `isbn13_from_isbn10` and add:

```python
def candidate_isbn10(candidate: SearchCandidate) -> str:
    return next(
        (
            value
            for value in candidate.isbns
            if len(value) == 10 and isbn13_from_isbn10(value) == candidate.isbn
        ),
        "",
    )


def candidate_isbn_summary(candidate: SearchCandidate) -> str:
    if not candidate.isbn:
        return ""
    lines = [f"建議 ISBN-13：{candidate.isbn}"]
    isbn10 = candidate_isbn10(candidate)
    if isbn10:
        lines.append(f"對應 ISBN-10：{isbn10}（同一版本對應碼）")
    return "\n".join(lines)
```

Create `edition_label` using only known data. Omit missing fields instead of guessing. Join classification reasons for the `判定` line.

In `_results_ready`, remove the `解析 ISBN：...` list. Report `找到 N 個候選版本` instead. In `_update_selection_summary`, append `將使用 ISBN-13 ...` and the corresponding ISBN-10 only for selected candidates.

- [ ] **Step 4: Re-run desktop tests**

Run: `python3.13 -m pytest desktop/tests/test_publisher_workflow.py desktop/tests/test_cover_search_free_sources.py -q`

Expected: PASS after updating any old assertion that expected `解析 ISBN：`.

- [ ] **Step 5: Commit**

```bash
git add desktop/tests/test_publisher_workflow.py python/src/epub_a4_word_desktop/cover/search_panel.py
git commit -m "fix: explain ISBN edition choices"
```

### Task 4: Regression verification and pull request

**Files:**
- Modify only if required by a failing regression test.

**Interfaces:**
- Produces: one reviewable branch and pull request; does not merge automatically.

- [ ] **Step 1: Run shared and desktop tests**

Run: `python3.13 -m pytest python-tests desktop/tests -q`

Expected: all tests pass with the existing intentional skips.

- [ ] **Step 2: Run structural checks**

```bash
python3.13 -m compileall python/src python-tests desktop/tests
python3.13 scripts/verify_project.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Push and open the pull request**

Use branch `fix/reference-back-cover-isbn-clarity` with base `main`. The PR body must state that no image was generated or bundled, list the fixed geometry ratios, explain the ISBN presentation rule, and include exact CI results.
