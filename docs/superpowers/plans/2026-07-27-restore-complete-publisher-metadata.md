# Restore Complete Publisher Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the complete PR #13 publisher workflow into the current `main` without losing PR #14's Logo rendering, CJK spine typography, source browse button, or tag-driven releases.

**Architecture:** Treat PR #13 as the owner of the expanded metadata schema, publisher UI, Logo search pipeline, and Android round-trip support. Resolve the ten textual merge conflicts by adapting PR #14's rendering and usability regressions to PR #13's focused `publisher_info_layout.py`, `spine_layout.py`, and metadata panel architecture.

**Tech Stack:** Python 3.13, PySide6, Pillow, pytest, Kotlin, Jetpack Compose, Chaquopy, Gradle 8.13, GitHub Actions.

## Global Constraints

- Preserve schema version 1 and load absent expanded metadata keys as empty strings.
- Display exactly one Desktop publisher metadata panel.
- Preserve user-adjusted element geometry during metadata refresh.
- Render publisher Logos on BACK and SPINE even in `front_only` mode.
- Render CJK spine strings per-character vertically; do not rotate them as one horizontal line.
- Keep `.github/workflows/release.yml` triggered only by `v*` tags.
- Publish the repaired result as `v0.6.1` only after all CI checks pass.

---

### Task 1: Add a Cross-Branch Metadata Contract

**Files:**
- Create: `python-tests/cover/test_complete_publisher_metadata_integration.py`

**Interfaces:**
- Consumes: `CoverMetadata`, `CoverProject`, `dumps_project(project)`, and `loads_project(text)`.
- Produces: a regression contract requiring all PR #13 metadata keys to survive schema-v1 JSON round-tripping.

- [ ] **Step 1: Write the failing shared-schema test**

```python
from dataclasses import replace

from epub_a4_word.cover.project_io import dumps_project, loads_project


def test_complete_publisher_metadata_round_trips(sample_project):
    project = sample_project()
    metadata = replace(
        project.metadata,
        translator="李彥樺",
        isbn_addon="00110",
        publisher_id="kadokawa-tw",
        english_title="Welcome to the Classroom",
        volume_number="2",
        arc_label="二年級篇",
        series_name="輕小說",
        internal_book_code="CL0308-17",
        spine_accent_color="#F15A24",
    )

    restored = loads_project(dumps_project(replace(project, metadata=metadata)))

    assert restored.metadata.translator == "李彥樺"
    assert restored.metadata.isbn_addon == "00110"
    assert restored.metadata.publisher_id == "kadokawa-tw"
    assert restored.metadata.english_title == "Welcome to the Classroom"
    assert restored.metadata.volume_number == "2"
    assert restored.metadata.arc_label == "二年級篇"
    assert restored.metadata.series_name == "輕小說"
    assert restored.metadata.internal_book_code == "CL0308-17"
    assert restored.metadata.spine_accent_color == "#F15A24"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
py -3.13 -m pytest python-tests/cover/test_complete_publisher_metadata_integration.py -q
```

Expected: FAIL because the current `CoverMetadata` does not accept `translator`, `publisher_id`, `english_title`, `volume_number`, `arc_label`, `series_name`, `internal_book_code`, or `spine_accent_color`.

- [ ] **Step 3: Commit the failing contract**

```powershell
git add python-tests/cover/test_complete_publisher_metadata_integration.py
git commit -m "test: require complete publisher metadata round trip"
```

---

### Task 2: Merge PR #13 and Restore the Shared Schema

**Files:**
- Modify: `python/src/epub_a4_word/cover/models.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Modify: `python/src/epub_a4_word/cover/publisher_info_layout.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Test: `python-tests/cover/test_complete_publisher_metadata_integration.py`
- Test: `python-tests/cover/test_publisher_metadata_overrides.py`
- Test: `python-tests/cover/test_template_metadata_refresh.py`

**Interfaces:**
- Consumes: PR #13 branch `origin/fix/reference-back-cover-isbn-clarity`.
- Produces: expanded `CoverMetadata`, backward-compatible JSON, publisher metadata overrides, and one refreshable publisher template.

- [ ] **Step 1: Start the merge without committing**

```powershell
git merge --no-ff --no-commit origin/fix/reference-back-cover-isbn-clarity
```

Expected: ten textual conflicts in Android, Desktop, shared templates, fonts, and tests.

- [ ] **Step 2: Resolve the shared metadata model**

Keep PR #13's complete `CoverMetadata` and `LogoAssetMetadata` definitions:

```python
translator: str = ""
isbn_addon: str = ""
publisher_id: str = ""
english_title: str = ""
volume_number: str = ""
arc_label: str = ""
series_name: str = ""
internal_book_code: str = ""
spine_accent_color: str = "#F15A24"
publisher_logo: LogoAssetMetadata | None = None
```

Keep matching `_metadata_from_dict` defaults and serialization in `project_io.py`.

- [ ] **Step 3: Resolve shared service and template behavior**

Retain PR #13's `PUBLISHER_METADATA_FIELDS`, metadata override handling, `publisher_info_layout.py`, and geometry-preserving template refresh. Retain PR #14's Logo element content flag:

```python
content={
    "path": resolved_path,
    "fit": "contain",
    "scale": 1.0,
    "clip_to_region": True,
}
```

Ensure the standard element ID set removes previous publisher elements before adding replacements.

- [ ] **Step 4: Run shared metadata tests**

```powershell
py -3.13 -m pytest `
  python-tests/cover/test_complete_publisher_metadata_integration.py `
  python-tests/cover/test_publisher_metadata_overrides.py `
  python-tests/cover/test_template_metadata_refresh.py `
  python-tests/cover/test_publisher_info_layout.py -q
```

Expected: PASS.

- [ ] **Step 5: Stage the shared schema resolution**

```powershell
git add python/src/epub_a4_word/cover python-tests/cover
git diff --cached --check
```

---

### Task 3: Restore the Desktop Publisher Workflow

**Files:**
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Add from PR #13: `python/src/epub_a4_word_desktop/cover/publisher_metadata_panel.py`
- Add from PR #13: `python/src/epub_a4_word_desktop/cover/publisher_logo_dialog.py`
- Add from PR #13: `python/src/epub_a4_word_desktop/cover/search_panel.py`
- Test: `desktop/tests/test_publisher_metadata_panel.py`
- Test: `desktop/tests/test_publisher_workflow.py`
- Test: `desktop/tests/test_publisher_logo_dialog.py`
- Test: `desktop/tests/test_cover_page.py`

**Interfaces:**
- Consumes: expanded shared metadata and Logo search/download services.
- Produces: one Desktop metadata panel, field-specific validation, Logo search/manual replacement, and a visible source browse button.

- [ ] **Step 1: Resolve Desktop controller and page conflicts**

Use PR #13's `PublisherMetadataPanel`, `PublisherLogoDialog`, metadata refresh, and publisher-change prompt. Keep PR #14's manual Logo controller entry point:

```python
def assign_publisher_logo(self, image_path: Path | str) -> CoverProject:
    copied = self._copy_asset(image_path)
    self.project = assign_publisher_logo(self.project, copied)
    return self.project
```

Keep a single call site that inserts `publisher_metadata_panel`; remove any duplicate legacy publisher form.

- [ ] **Step 2: Preserve the source browse button sizing**

Keep:

```python
self.browse_button.setMinimumWidth(88)
self.browse_button.setSizePolicy(
    QSizePolicy.Policy.Fixed,
    QSizePolicy.Policy.Fixed,
)
```

- [ ] **Step 3: Preserve real vertical Desktop canvas drawing**

Retain `vertical_text_lines(text)` and draw one character per line for content whose `direction` is `"vertical"`. Do not rotate CJK text through `QGraphicsTextItem`.

- [ ] **Step 4: Run Desktop publisher tests**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
py -3.13 -m pytest `
  desktop/tests/test_publisher_metadata_panel.py `
  desktop/tests/test_publisher_workflow.py `
  desktop/tests/test_publisher_logo_dialog.py `
  desktop/tests/test_cover_page.py `
  desktop/tests/test_cover_canvas.py -q
```

Expected: PASS with exactly one metadata panel.

- [ ] **Step 5: Stage the Desktop resolution**

```powershell
git add python/src/epub_a4_word_desktop desktop/tests
git diff --cached --check
```

---

### Task 4: Restore Android Metadata Round-Tripping

**Files:**
- Modify: `app/src/main/java/tw/daniel/epubword/MainActivity.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/model/CoverModels.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/model/CoverProjectJson.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverSetupScreen.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/python/PythonCoverGateway.kt`
- Modify: `app/src/main/python/android_bridge.py`
- Test: `app/src/test/java/tw/daniel/epubword/cover/model/CoverProjectJsonTest.kt`
- Test: `app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewModelTest.kt`

**Interfaces:**
- Consumes: schema-v1 JSON keys from the shared Python project.
- Produces: Kotlin metadata models and Compose fields that round-trip the same values without dropping unknown optional fields.

- [ ] **Step 1: Resolve Android models and JSON**

Keep PR #13's expanded `CoverMetadata` properties and encode/decode keys. Preserve defaults so an old schema-v1 fixture without the new keys still decodes.

- [ ] **Step 2: Resolve Android setup and ViewModel**

Keep PR #13's metadata state fields and `.put(...)` calls for all publisher keys. Keep PR #14's `assignPublisherLogo(uri)` bridge call and Wikimedia search intent.

- [ ] **Step 3: Resolve Android activity and Python bridge**

Keep the document picker for local Logo selection, the browser search launcher, and PR #13's expanded metadata settings passed to `new_project`.

- [ ] **Step 4: Run Android unit tests**

```powershell
$gradle = Resolve-Path '..\gradle-8.13\bin\gradle.bat'
$python = Resolve-Path '..\uv-python\cpython-3.13-windows-x86_64-none\python.exe'
$env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
& $gradle --no-daemon :app:testDebugUnitTest `
  -PchaquopyBuildPython="$python" --console=plain
```

Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 5: Stage the Android resolution**

```powershell
git add app/src
git diff --cached --check
```

---

### Task 5: Reconcile Reference Spine Rendering

**Files:**
- Modify: `python/src/epub_a4_word/cover/fonts.py`
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word/cover/spine_layout.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Test: `python-tests/cover/test_publisher_spine_template.py`
- Test: `python-tests/cover/test_user_reported_publisher_typography.py`
- Test: `python-tests/cover/test_render.py`

**Interfaces:**
- Consumes: PR #13 `SpineSlot` roles and PR #14 vertical renderer.
- Produces: tiered spine content with reference-sized CJK typography and visible Logos.

- [ ] **Step 1: Add the wide-spine regression expectation**

Ensure the full-tier test asserts:

```python
assert title.content["direction"] == "vertical"
assert title.content["font_size_pt"] >= 14.0
assert author.content["font_size_pt"] >= 10.0
assert publisher.content["font_size_pt"] >= 10.0
```

- [ ] **Step 2: Run the spine test and verify RED**

```powershell
py -3.13 -m pytest `
  python-tests/cover/test_publisher_spine_template.py `
  python-tests/cover/test_user_reported_publisher_typography.py -q
```

Expected: FAIL because PR #13's full tier uses 8pt title and smaller author/publisher sizes.

- [ ] **Step 3: Adjust `build_spine_slots` without removing roles**

For width at least 10mm, retain PR #13's title, English title, volume, arc, author, internal code, and publisher roles while using at least 14pt, 10pt, and 10pt for the main CJK title, author, and publisher. Keep the spine Logo at the top and compute its width as 70% of the physical spine.

- [ ] **Step 4: Verify Logo clipping and vertical rendering**

```powershell
py -3.13 -m pytest `
  python-tests/cover/test_render.py::test_publisher_logo_renders_on_back_in_front_only_mode `
  python-tests/cover/test_publisher_back_template.py `
  python-tests/cover/test_publisher_spine_template.py `
  python-tests/cover/test_user_reported_publisher_typography.py -q
```

Expected: PASS.

- [ ] **Step 5: Stage the rendering resolution**

```powershell
git add python/src/epub_a4_word/cover python-tests/cover
git diff --cached --check
```

---

### Task 6: Complete the Merge and Run Full Verification

**Files:**
- Verify: all files staged by Tasks 2–5
- Preserve: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: all resolved integration changes.
- Produces: one merge commit whose tree contains PR #13 plus PR #14 regressions.

- [ ] **Step 1: Confirm every merge conflict is resolved**

```powershell
if (git diff --name-only --diff-filter=U) {
    throw "Unresolved merge conflicts remain"
}
git status --short
```

- [ ] **Step 2: Run complete Python and Desktop suites**

```powershell
py -3.13 -m pytest python-tests -q
$env:QT_QPA_PLATFORM='offscreen'
py -3.13 -m pytest desktop/tests -q
```

Expected: zero failures.

- [ ] **Step 3: Build Android**

```powershell
& $gradle --no-daemon :app:testDebugUnitTest :app:assembleDebug `
  -PchaquopyBuildPython="$python" --console=plain
```

Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Run static and project verification**

```powershell
py -3.13 -m compileall -q python/src app/src/main/python
py -3.13 scripts/verify_project.py
git show HEAD:.github/workflows/release.yml | Select-String 'tags: \["v\*"\]'
git diff --cached --check
```

- [ ] **Step 5: Complete the merge commit**

```powershell
git commit -m "fix: restore complete publisher metadata"
```

---

### Task 7: Publish, Merge, and Release `v0.6.1`

**Files:**
- Publish: branch `fix/restore-complete-publisher-metadata`

**Interfaces:**
- Consumes: verified merge commit.
- Produces: repair PR, merged `main`, `v0.6.1` tag, and release assets.

- [ ] **Step 1: Push the repair branch**

```powershell
git push -u origin fix/restore-complete-publisher-metadata
```

- [ ] **Step 2: Open a PR against `main`**

Create a ready-for-review PR describing the missing-field root cause, conflict rules, and full verification evidence.

- [ ] **Step 3: Wait for all required CI**

Require Desktop PySide6 tests, Android debug APK, and Windows portable EXE to conclude `success`.

- [ ] **Step 4: Squash-merge with an expected head SHA**

Use GitHub's merge API with `expected_head_sha` equal to the verified branch head.

- [ ] **Step 5: Tag the merged main commit**

```powershell
git fetch origin main --tags
git tag -a v0.6.1 origin/main -m "EPUB2A4 v0.6.1"
git push origin refs/tags/v0.6.1
```

- [ ] **Step 6: Verify the release**

Require the `v0.6.1` Release workflow to conclude `success` and confirm these exact assets:

```text
EPUB2A4-Android.apk
EPUB2A4-Windows-Portable-x64.zip
SHA256SUMS.txt
```
