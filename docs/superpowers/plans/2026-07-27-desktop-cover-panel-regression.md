# Desktop Cover Panel Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a visible source browse button and exactly one publisher metadata panel in the Windows Desktop cover editor.

**Architecture:** `CoverSetupPanel` remains the owner of the publisher panel. `CoverPage` aliases that object for its existing signal wiring, while the right sidebar preserves enough width for the source row.

**Tech Stack:** Python 3.13, PySide6 6.11.1, pytest, pytest-qt, PyInstaller

## Global Constraints

- `CoverPage` must contain exactly one `PublisherMetadataPanel`.
- Existing metadata and Logo signal wiring must continue using `CoverPage.publisher_metadata_panel`.
- At 1200 × 800, the complete browse button must be visible in the right viewport.
- Publish the verified repair as v0.6.2.

---

### Task 1: Reproduce both Desktop layout regressions

**Files:**
- Modify: `desktop/tests/test_cover_page.py`

**Interfaces:**
- Consumes: `CoverPage.publisher_metadata_panel`, `CoverPage.setup_panel.publisher_metadata_panel`, and `CoverPage.right_scroll`
- Produces: two regression tests that fail on v0.6.1

- [ ] **Step 1: Add the duplicate-panel regression test**

```python
def test_cover_page_uses_one_shared_publisher_metadata_panel(qtbot) -> None:
    page = CoverPage()
    qtbot.addWidget(page)

    panels = page.findChildren(PublisherMetadataPanel)

    assert len(panels) == 1
    assert page.publisher_metadata_panel is page.setup_panel.publisher_metadata_panel
```

- [ ] **Step 2: Add the visible browse-button regression test**

```python
def test_cover_page_keeps_source_browse_button_inside_right_viewport(qtbot) -> None:
    page = CoverPage()
    qtbot.addWidget(page)
    page.resize(1200, 800)
    page.show()
    qtbot.wait(1)

    button = page.setup_panel.browse_button
    top_left = button.mapTo(page.right_scroll.viewport(), button.rect().topLeft())
    bottom_right = button.mapTo(page.right_scroll.viewport(), button.rect().bottomRight())

    assert button.isVisible()
    assert top_left.x() >= 0
    assert bottom_right.x() < page.right_scroll.viewport().width()
```

- [ ] **Step 3: Run both tests and verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
..\uv\uv.exe run pytest desktop/tests/test_cover_page.py -q
```

Expected: duplicate count is 2 and the browse button lies outside the right viewport.

### Task 2: Share the panel and preserve sidebar width

**Files:**
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Test: `desktop/tests/test_cover_page.py`

**Interfaces:**
- Consumes: `CoverSetupPanel.publisher_metadata_panel`
- Produces: `CoverPage.publisher_metadata_panel` as an alias to the sole panel

- [ ] **Step 1: Replace the second panel with an alias**

```python
self.setup_panel = CoverSetupPanel(self)
self.publisher_metadata_panel = self.setup_panel.publisher_metadata_panel
self.publisher_metadata_panel.setEnabled(False)
```

Remove the second `PublisherMetadataPanel(self)` construction and remove the second `right_layout.addWidget(self.publisher_metadata_panel)` call.

- [ ] **Step 2: Make the source editor shrink before the button**

```python
self.source_edit.setMinimumWidth(0)
self.source_edit.setSizePolicy(
    QSizePolicy.Policy.Ignored,
    QSizePolicy.Policy.Preferred,
)
```

- [ ] **Step 3: Preserve a usable right sidebar**

```python
self.right_scroll.setMinimumWidth(330)
self.splitter.setCollapsible(2, False)
```

- [ ] **Step 4: Run the regression tests and verify GREEN**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
..\uv\uv.exe run pytest desktop/tests/test_cover_page.py desktop/tests/test_publisher_metadata_panel.py desktop/tests/test_publisher_workflow.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the functional repair**

```powershell
git add desktop/tests/test_cover_page.py python/src/epub_a4_word_desktop/pages/cover_page.py python/src/epub_a4_word_desktop/cover/setup_panel.py
git commit -m "fix: keep cover source browse and publisher panel visible"
```

### Task 3: Verify and publish v0.6.2

**Files:**
- Modify: `pyproject.toml`
- Modify: `python/src/epub_a4_word/__init__.py`
- Modify: `app/build.gradle.kts`
- Modify: `python-tests/test_android_bridge.py`

**Interfaces:**
- Consumes: existing tag-triggered `.github/workflows/release.yml`
- Produces: Desktop and Android version 0.6.2 release assets

- [ ] **Step 1: Bump release versions**

Set the Python package and core version to `0.6.2`; set Android `versionName`
to `0.6.2` and increment `versionCode` from `4` to `5`; update the bridge
version assertion to `0.6.2`.

- [ ] **Step 2: Run the complete test suites**

```powershell
$env:PYTHONPATH="$pwd;python/src;app/src/main/python"
..\uv\uv.exe run pytest python-tests -q
$env:QT_QPA_PLATFORM='offscreen'
..\uv\uv.exe run pytest desktop/tests -q
```

- [ ] **Step 3: Build and verify both deliverables**

```powershell
..\gradle-8.13\bin\gradle.bat --no-daemon :app:testDebugUnitTest :app:assembleDebug
..\uv\uv.exe run python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec
..\uv\uv.exe run python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64
```

- [ ] **Step 4: Commit, push, merge, and tag**

Commit the version bump, push `fix/desktop-cover-panel-regression`, open a PR
against `main`, wait for all GitHub checks, squash-merge, then create and push
the annotated `v0.6.2` tag.

- [ ] **Step 5: Verify Release assets**

Confirm the published release contains:

- `EPUB2A4-Android.apk`
- `EPUB2A4-Windows-Portable-x64.zip`
- `SHA256SUMS.txt`
