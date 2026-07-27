# Readable Bounded Spine Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make spine text and the publisher Logo readable on a 6.030 mm spine while keeping every generated element completely inside the physical spine.

**Architecture:** Keep the physical spine and panel fold geometry unchanged. Change only the shared spine-safe rectangle to use an adaptive horizontal inset, then enlarge the publisher Logo using the physical spine rectangle; all Desktop, Android, preview, and export consumers inherit the corrected shared geometry.

**Tech Stack:** Python 3.13, pytest, PySide6 6.11.1, Kotlin/Gradle 8.13, PyInstaller, GitHub Actions

## Global Constraints

- Front and back panel fold clearance remains `3 mm`.
- Spine horizontal inset is `min(1.0 mm, spine_width_mm × 0.12)` per side.
- Spine vertical inset remains `5 mm` at the top and bottom.
- Publisher Logo width is `90%` of the physical spine width.
- Publisher Logo height is at most `18 mm`.
- Text and Logo rectangles must lie completely inside `spine_rect`; clipping is not accepted as the boundary mechanism.
- Existing vertical text direction, spine width, fold positions, background, and Logo aspect ratio remain unchanged.
- Publish the repair as `v0.6.4` for Desktop and Android.

---

### Task 1: Adaptive spine text safe rectangle

**Files:**
- Modify: `python-tests/cover/test_geometry.py`
- Modify: `python-tests/cover/test_publisher_spine_template.py`
- Modify: `python/src/epub_a4_word/cover/geometry.py`

**Interfaces:**
- Consumes: `calculate_layout(project: CoverProject) -> CoverLayout`
- Produces: `CoverLayout.spine_safe_rect` with the adaptive horizontal inset

- [ ] **Step 1: Add exact failing geometry tests**

Add parameterized assertions to `test_geometry.py`:

```python
@pytest.mark.parametrize(
    ("width_mm", "expected_inset_mm"),
    [(4.0, 0.48), (6.03, 0.7236), (8.0, 0.96), (12.0, 1.0)],
)
def test_spine_safe_rect_uses_adaptive_horizontal_inset(
    sample_project,
    width_mm: float,
    expected_inset_mm: float,
) -> None:
    layout = calculate_layout(sample_project(manual_spine_width_mm=width_mm))

    assert layout.spine_safe_rect.x_mm == pytest.approx(
        layout.spine_rect.x_mm + expected_inset_mm
    )
    assert layout.spine_safe_rect.width_mm == pytest.approx(
        width_mm - 2.0 * expected_inset_mm
    )
```

Add the reported automatic-width case:

```python
def test_133_pages_at_point_09_mm_keeps_readable_spine_width(sample_project) -> None:
    layout = calculate_layout(
        sample_project(
            page_count=133,
            paper_caliper_mm=0.09,
            manual_spine_width_mm=None,
        )
    )

    assert layout.spine_width_mm == pytest.approx(6.03)
    assert layout.spine_safe_rect.width_mm == pytest.approx(4.5828)
```

- [ ] **Step 2: Run the geometry tests and verify RED**

Run:

```powershell
$env:PYTHONPATH="$pwd;python/src;app/src/main/python"
& '..\uv\uv.exe' run pytest python-tests/cover/test_geometry.py -q
```

Expected: the 6.03 mm case reports `0.03 mm` instead of `4.5828 mm`, and the other adaptive-width assertions also fail.

- [ ] **Step 3: Implement the adaptive inset**

In `geometry.py`, retain `SPINE_FOLD_SAFE_INSET_MM = 3.0` for front/back panels and add a spine-only cap:

```python
SPINE_CONTENT_MAX_INSET_MM = 1.0
SPINE_CONTENT_INSET_RATIO = 0.12


def _spine_safe_rect(spine: RectMm) -> RectMm:
    horizontal_inset = min(
        SPINE_CONTENT_MAX_INSET_MM,
        spine.width_mm * SPINE_CONTENT_INSET_RATIO,
    )
    return spine.inset(
        horizontal_inset,
        DEFAULT_SAFE_INSET_MM,
        horizontal_inset,
        DEFAULT_SAFE_INSET_MM,
    )
```

- [ ] **Step 4: Add compact-template boundary assertions**

In `test_publisher_spine_template.py`, build the exact reported project and assert each generated text rectangle is readable and bounded:

```python
def test_reported_603_spine_text_is_readable_and_bounded(sample_project) -> None:
    project = replace(
        sample_project(
            page_count=133,
            paper_caliper_mm=0.09,
            manual_spine_width_mm=None,
        ),
        metadata=CoverMetadata(
            title="魔法禁書目錄 1",
            author="鎌池和馬",
            publisher="台灣角川",
            volume_number="1",
        ),
    )
    result = apply_template(project, "publisher_back_matter_with_spine")
    spine = calculate_layout(result).spine_rect

    for element_id in (
        "spine-title-main",
        "spine-volume",
        "spine-author",
        "spine-publisher-name",
    ):
        transform = result.elements_by_id[element_id].transform
        assert transform.width_mm >= 4.5
        assert transform.x_mm >= spine.x_mm
        assert transform.x_mm + transform.width_mm <= spine.right_mm
        assert transform.y_mm >= spine.y_mm
        assert transform.y_mm + transform.height_mm <= spine.bottom_mm
```

Import `calculate_layout` in the test file.

- [ ] **Step 5: Run Task 1 tests and verify GREEN**

Run:

```powershell
& '..\uv\uv.exe' run pytest python-tests/cover/test_geometry.py python-tests/cover/test_publisher_spine_template.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add python/src/epub_a4_word/cover/geometry.py python-tests/cover/test_geometry.py python-tests/cover/test_publisher_spine_template.py
git commit -m "fix: keep narrow spine text readable"
```

### Task 2: Larger publisher Logo within spine boundaries

**Files:**
- Modify: `python-tests/cover/test_publisher_spine_template.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`

**Interfaces:**
- Consumes: `CoverProject.metadata.publisher_logo` and `CoverLayout.spine_rect`
- Produces: `spine-publisher-logo` at `90%` spine width, at most `18 mm` high, centered and bounded

- [ ] **Step 1: Add a failing Logo geometry test**

Create a temporary PNG, assign it through `LogoAssetMetadata`, and assert:

```python
def test_reported_603_spine_logo_is_large_centered_and_bounded(
    sample_project,
    tmp_path,
) -> None:
    logo_path = tmp_path / "publisher.png"
    Image.new("RGBA", (300, 120), "navy").save(logo_path)
    project = replace(
        sample_project(
            page_count=133,
            paper_caliper_mm=0.09,
            manual_spine_width_mm=None,
        ),
        metadata=replace(
            sample_project().metadata,
            publisher="台灣角川",
            publisher_logo=LogoAssetMetadata(
                asset_id="publisher-logo",
                path=str(logo_path),
            ),
        ),
    )
    result = apply_template(project, "publisher_back_matter_with_spine")
    spine = calculate_layout(result).spine_rect
    logo = result.elements_by_id["spine-publisher-logo"].transform

    assert logo.width_mm == pytest.approx(spine.width_mm * 0.90)
    assert logo.height_mm <= 18.0
    assert logo.x_mm == pytest.approx(
        spine.x_mm + (spine.width_mm - logo.width_mm) / 2.0
    )
    assert logo.x_mm >= spine.x_mm
    assert logo.x_mm + logo.width_mm <= spine.right_mm
    assert logo.y_mm >= spine.y_mm
    assert logo.y_mm + logo.height_mm <= spine.bottom_mm
```

Import `PIL.Image` and `LogoAssetMetadata`.

- [ ] **Step 2: Run the Logo test and verify RED**

Run:

```powershell
& '..\uv\uv.exe' run pytest python-tests/cover/test_publisher_spine_template.py::test_reported_603_spine_logo_is_large_centered_and_bounded -q
```

Expected: width is `70%` rather than `90%`.

- [ ] **Step 3: Implement the bounded Logo size**

In `_publisher_spine_elements()` in `templates.py`, replace the existing Logo dimensions with:

```python
logo_width = layout.spine_rect.width_mm * 0.90
logo_height = min(18.0, layout.spine_safe_rect.height_mm * 0.10)
logo_rect = RectMm(
    layout.spine_rect.x_mm
    + (layout.spine_rect.width_mm - logo_width) / 2.0,
    layout.spine_safe_rect.y_mm,
    logo_width,
    logo_height,
)
```

Keep `fit: "contain"` and `clip_to_region: True`; the test proves the underlying rectangle is already bounded.

- [ ] **Step 4: Run Task 2 tests and verify GREEN**

Run:

```powershell
& '..\uv\uv.exe' run pytest python-tests/cover/test_publisher_spine_template.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add python/src/epub_a4_word/cover/templates.py python-tests/cover/test_publisher_spine_template.py
git commit -m "fix: enlarge bounded publisher spine Logo"
```

### Task 3: Verify and publish v0.6.4

**Files:**
- Modify: `pyproject.toml`
- Modify: `python/src/epub_a4_word/__init__.py`
- Modify: `app/build.gradle.kts`
- Modify: `python-tests/test_android_bridge.py`

**Interfaces:**
- Consumes: tag-triggered `.github/workflows/release.yml`
- Produces: Desktop and Android version `0.6.4`, Android `versionCode = 7`, tag `v0.6.4`

- [ ] **Step 1: Bump version metadata**

Change:

```text
pyproject.toml: 0.6.3 -> 0.6.4
python/src/epub_a4_word/__init__.py: 0.6.3 -> 0.6.4
app/build.gradle.kts: versionCode 6 -> 7
app/build.gradle.kts: versionName 0.6.3 -> 0.6.4
python-tests/test_android_bridge.py: expected 0.6.3 -> 0.6.4
```

- [ ] **Step 2: Run complete test suites**

Run:

```powershell
$env:PYTHONPATH="$pwd;python/src;app/src/main/python"
$env:QT_QPA_PLATFORM="offscreen"
& '..\uv\uv.exe' run pytest python-tests -q
& '..\uv\uv.exe' run pytest desktop/tests -q
```

Expected: both suites pass with zero failures.

- [ ] **Step 3: Build Android**

Run:

```powershell
$env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
$env:CHAQUOPY_PYTHON=(Resolve-Path '..\uv-python\cpython-3.13.14-windows-x86_64-none\python.exe').Path
& '..\gradle-8.13\bin\gradle.bat' --no-daemon :app:testDebugUnitTest :app:assembleDebug
```

Expected: `BUILD SUCCESSFUL` and `app/build/outputs/apk/debug/app-debug.apk` exists.

- [ ] **Step 4: Build and verify Windows Portable**

Run:

```powershell
& '..\uv\uv.exe' run python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec
New-Item -ItemType File -Path "dist/EPUB2A4-Windows-Portable-x64/portable.flag" -Force | Out-Null
& '..\uv\uv.exe' run python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64
& "dist/EPUB2A4-Windows-Portable-x64/EPUB2A4.exe" --portable-smoke-test
```

Expected: verification exits `0` and the smoke test exits `0`.

- [ ] **Step 5: Commit the version bump**

```powershell
git add pyproject.toml python/src/epub_a4_word/__init__.py app/build.gradle.kts python-tests/test_android_bridge.py
git commit -m "chore: prepare v0.6.4"
```

- [ ] **Step 6: Push, merge, tag, and verify Release**

Push `fix/spine-text-width-v064`, create a ready PR against `main`, wait for Desktop, Android, and Windows CI, squash-merge, then create annotated tag `v0.6.4` on the merge commit.

Verify the Release workflow succeeds and these assets resolve:

```text
EPUB2A4-Android.apk
EPUB2A4-Windows-Portable-x64.zip
SHA256SUMS.txt
```
