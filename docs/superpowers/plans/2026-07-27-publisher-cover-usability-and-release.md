# Publisher Cover Usability and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make publisher-back covers usable and readable on desktop and Android, then publish both binaries for version tags.

**Architecture:** Python cover core owns template identity, Logo placement, and spine typography. PySide6 and Compose supply native UI actions for that shared project JSON. A tag-only Actions workflow builds the existing Windows portable package and Android APK, computes checksums, and creates one Release.

**Tech Stack:** Python 3.13, Pillow, PySide6, pytest, Kotlin, Compose, JUnit, Gradle, GitHub Actions.

## Global Constraints

- Preserve schema-v1 and use no unverified or paid Logo API.
- The publisher template owns one publisher-info element and at most one Logo element.
- Chinese spine titles are vertical; Latin-only subtitles use 90-degree rotation; primary spine text is at least 8 pt when shown.
- Only pushed `v*` tags create Releases.

---

### Task 1: Core template and Logo contract

**Files:**
- Modify: `python/src/epub_a4_word/cover/templates.py`, `python/src/epub_a4_word/cover/service.py`
- Test: `python-tests/cover/test_publisher_back_template.py`, `python-tests/cover/test_templates.py`

**Interfaces:** `assign_publisher_logo(project: CoverProject, path: str) -> CoverProject` replaces the image element `back-publisher-logo`.

- [ ] **Step 1: Write failing tests**

```python
def test_publisher_logo_is_replaced_not_duplicated(sample_project, tmp_path):
    project = apply_template(sample_project(), "publisher_back_matter")
    project = assign_publisher_logo(project, str(tmp_path / "logo.png"))
    assert [e.id for e in project.elements].count("back-publisher-logo") == 1

def test_spine_title_is_vertical_and_readable(sample_project):
    title = apply_template(sample_project(manual_spine_width_mm=8), "minimal_text").elements_by_id["spine-title"]
    assert title.content["direction"] == "vertical"
    assert title.content["font_size_pt"] >= 8
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=python/src python -m pytest python-tests/cover/test_publisher_back_template.py python-tests/cover/test_templates.py -q`

Expected: FAIL because the Logo assignment function and vertical spine behavior are absent.

- [ ] **Step 3: Implement GREEN**

```python
def assign_publisher_logo(project: CoverProject, path: str) -> CoverProject:
    slot = project.background["publisher_logo_slot"]
    logo = CoverElement("back-publisher-logo", ElementKind.IMAGE, Region.BACK,
        ElementTransform(**slot), z_index=30,
        content={"path": path, "fit": "contain", "scale": 1.0})
    return replace(project, elements=tuple(e for e in project.elements if e.id != logo.id) + (logo,))
```

Add the Logo ID to `STANDARD_TEMPLATE_IDS`; set Chinese `spine-title` to `direction="vertical"`, use 10 pt at 8 mm or wider, and omit author before lowering the title below 8 pt.

- [ ] **Step 4: Verify GREEN and commit**

Run: `PYTHONPATH=python/src python -m pytest python-tests/cover/test_publisher_back_template.py python-tests/cover/test_templates.py -q`

```bash
git add python/src/epub_a4_word/cover python-tests/cover/test_publisher_back_template.py python-tests/cover/test_templates.py
git commit -m "feat: improve publisher template and spine readability"
```

### Task 2: Desktop publisher controls

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/publisher_panel.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`, `python/src/epub_a4_word_desktop/pages/cover_page.py`, `python/src/epub_a4_word_desktop/cover/controller.py`
- Test: `desktop/tests/test_cover_page.py`, `desktop/tests/test_publisher_workflow.py`

**Interfaces:** `PublisherPanel.logo_selected: Signal(str)` and `CoverController.assign_publisher_logo(path: str) -> None`.

- [ ] **Step 1: Write failing tests**

```python
def test_setup_browse_button_remains_visible(qtbot):
    panel = CoverSetupPanel(); qtbot.addWidget(panel); panel.resize(320, 600); panel.show()
    assert panel.browse_button.isVisible()
    assert panel.browse_button.geometry().right() <= panel.width()

def test_manual_logo_selection_updates_single_logo(qtbot, tmp_path):
    page = CoverPage(tmp_path); qtbot.addWidget(page)
    page.controller.replace_project(dumps_project(_publisher_project(tmp_path)))
    page._apply_publisher_logo(str(tmp_path / "logo.png"))
    assert "back-publisher-logo" in loads_project(page.controller.project_json).elements_by_id
```

- [ ] **Step 2: Verify RED**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=python/src python -m pytest desktop/tests/test_cover_page.py desktop/tests/test_publisher_workflow.py -q`

Expected: FAIL because the panel action is absent.

- [ ] **Step 3: Implement GREEN**

Create one `PublisherPanel` containing metadata fields, Logo search button, manual selection button, and status. Manual selection uses `QFileDialog.getOpenFileName` with PNG/JPEG/WebP filters. Both actions call the controller assignment API and refresh the canvas. Remove the second publisher form. Keep the source row as stretchable edit followed by a non-shrinking browse button.

- [ ] **Step 4: Verify GREEN and commit**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=python/src python -m pytest desktop/tests/test_cover_page.py desktop/tests/test_publisher_workflow.py -q`

```bash
git add python/src/epub_a4_word_desktop desktop/tests/test_cover_page.py desktop/tests/test_publisher_workflow.py
git commit -m "fix: make desktop publisher logo workflow usable"
```

### Task 3: Android publisher controls

**Files:**
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverSetupScreen.kt`, `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt`, `app/src/main/java/tw/daniel/epubword/MainActivity.kt`
- Test: `app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewModelTest.kt`

**Interfaces:** `CoverSetupCallbacks.onChoosePublisherLogo: () -> Unit`; `CoverViewModel.assignPublisherLogo(path: String)`.

- [ ] **Step 1: Write failing test**

```kotlin
@Test fun publisherTemplateLogoUpdatesProjectJson() {
    viewModel.setTemplate("publisher_back_matter")
    viewModel.createProject()
    viewModel.assignPublisherLogo("/data/user/0/test/logo.png")
    assertTrue(viewModel.uiState.value.projectJson!!.contains("back-publisher-logo"))
}
```

- [ ] **Step 2: Verify RED**

Run: `./gradlew :app:testDebugUnitTest --tests '*CoverViewModelTest.publisherTemplateLogoUpdatesProjectJson'`

Expected: FAIL because Android does not expose the publisher template or Logo mutation.

- [ ] **Step 3: Implement GREEN**

Add `publisher_back_matter` to `TEMPLATE_OPTIONS`; show one publisher card only for that template. Register `ActivityResultContracts.GetContent()` in `MainActivity`, copy the URI to app-controlled storage, and call the view-model method. Use Python bridge output as the preview source; do not create a second Android-only publisher-info block.

- [ ] **Step 4: Verify GREEN and commit**

Run: `./gradlew :app:testDebugUnitTest --tests '*CoverViewModelTest.publisherTemplateLogoUpdatesProjectJson'`

```bash
git add app/src/main/java/tw/daniel/epubword app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewModelTest.kt
git commit -m "feat: add Android publisher logo selection"
```

### Task 4: Tag-triggered release workflow

**Files:**
- Create: `.github/workflows/release.yml`
- Test: `python-tests/test_verify_project.py`

- [ ] **Step 1: Write failing assertion**

```python
def test_release_workflow_uploads_both_platforms():
    text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "v*" in text and "EPUB2A4-Windows-Portable-x64.zip" in text
    assert "EPUB2A4-release.apk" in text and "SHA256SUMS.txt" in text
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=python/src python -m pytest python-tests/test_verify_project.py -q`

Expected: FAIL because `release.yml` is absent.

- [ ] **Step 3: Implement GREEN**

```yaml
on:
  push:
    tags: ["v*"]
permissions:
  contents: write
```

Build portable Windows ZIP and `:app:assembleRelease` in separate jobs; download both in a release job, create `SHA256SUMS.txt`, and use `softprops/action-gh-release` to attach both binaries and checksum file with generated notes.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python scripts/verify_project.py`

```bash
git add .github/workflows/release.yml python-tests/test_verify_project.py
git commit -m "ci: publish desktop and Android releases from tags"
```

### Task 5: Complete verification and reference-layout inspection

- [ ] **Step 1: Run Python and desktop suites**

Run: `PYTHONPATH=python/src:app/src/main/python python -m pytest python-tests -q && QT_QPA_PLATFORM=offscreen PYTHONPATH=python/src:app/src/main/python python -m pytest desktop/tests -q`

- [ ] **Step 2: Run Android tests and assemble**

Run: `./gradlew :app:testDebugUnitTest :app:assembleRelease`

- [ ] **Step 3: Inspect publisher export**

Run: `PYTHONPATH=python/src python scripts/inspect_cover_exports.py <generated-publisher-cover.pdf>`

Expected: one publisher block, one centered Logo slot, a vertical readable Chinese title, and bottom publisher identification matching the supplied reference hierarchy.
