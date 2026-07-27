# Logo Import and Publisher Information Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair Desktop Logo import/search and make newly entered translator, price, and agency information readable without resetting user placement.

**Architecture:** Shared Logo download functions gain an optional validated SVG-to-PNG conversion hook. Publisher template refresh expands its two layout-dependent text rectangles while preserving their horizontal placement, and typography defaults rise to 10/9 pt.

**Tech Stack:** Python 3.13, Pillow 11, PySide6 6.11.1, pytest, pytest-qt, PyInstaller

## Global Constraints

- SVG active-content validation must run before the converter.
- Raster Logo imports must not invoke the SVG converter.
- Publisher heading is 10 pt and details are 9 pt when they fit.
- Metadata refresh preserves user X/Y placement and width, except details move down by heading height growth.
- Publish the verified repair as v0.6.3.

---

### Task 1: Restore the Logo conversion API

**Files:**
- Modify: `python/src/epub_a4_word/cover/search/logo_download.py`
- Modify: `python-tests/cover/test_publisher_logo_download.py`
- Modify: `desktop/tests/test_publisher_logo_embedding.py`

**Interfaces:**
- Consumes: `rasterize_svg_logo(data: bytes, width: int, height: int) -> bytes`
- Produces: `download_logo(..., svg_converter: SvgConverter | None = None)` and `import_logo_file(..., svg_converter: SvgConverter | None = None)`

- [ ] **Step 1: Add failing shared API tests**

Add tests that import PNG with a converter that raises if called, and import
SVG with a recording converter returning PNG bytes. Assert the PNG remains PNG,
the SVG becomes PNG, and the stored suffix is `.png`.

- [ ] **Step 2: Add the failing controller regression**

Create a publisher-template project, call
`CoverController.apply_manual_publisher_logo()` with a PNG, and assert the
project receives publisher Logo metadata. On v0.6.2 this must fail with
`unexpected keyword argument 'svg_converter'`.

- [ ] **Step 3: Run tests and verify RED**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
..\uv\uv.exe run pytest python-tests/cover/test_publisher_logo_download.py desktop/tests/test_publisher_logo_embedding.py -q
```

- [ ] **Step 4: Implement the optional converter**

Declare:

```python
SvgConverter = Callable[[bytes, int, int], bytes]
```

After `_validate_svg(data)`, call the converter when provided, validate its
result through `_validate_raster()`, and store the returned PNG bytes using a
`.png` suffix. Thread the same keyword from `import_logo_file()` into
`download_logo()`.

- [ ] **Step 5: Run tests and verify GREEN**

Run the Task 1 command and require all tests to pass.

- [ ] **Step 6: Commit**

```powershell
git add python/src/epub_a4_word/cover/search/logo_download.py python-tests/cover/test_publisher_logo_download.py desktop/tests/test_publisher_logo_embedding.py
git commit -m "fix: restore validated SVG Logo conversion"
```

### Task 2: Expand publisher information during metadata refresh

**Files:**
- Modify: `python/src/epub_a4_word/cover/publisher_info_layout.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Modify: `python-tests/cover/test_publisher_info_layout.py`
- Modify: `python-tests/cover/test_template_metadata_refresh.py`
- Modify: `python-tests/cover/test_user_reported_publisher_typography.py`

**Interfaces:**
- Consumes: generated `back-publisher-heading` and `back-publisher-details`
- Produces: 10/9 pt defaults and expanded transforms during `refresh_template_metadata()`

- [ ] **Step 1: Add failing typography tests**

Assert that a normal publisher heading is 10 pt and price, agency, and
translator details are 9 pt.

- [ ] **Step 2: Add the failing translator refresh test**

Apply the publisher template without translator, record the details rectangle,
then refresh metadata with `translator="李彥樺"`. Assert the text contains
`譯者：李彥樺`, its height increases, X/Y/width remain unchanged, and no line
lies beyond the new rectangle.

- [ ] **Step 3: Add the failing heading-growth test**

Refresh a short publisher name to one that wraps. Assert heading height grows
and details Y moves down by the same delta.

- [ ] **Step 4: Run tests and verify RED**

```powershell
..\uv\uv.exe run pytest python-tests/cover/test_publisher_info_layout.py python-tests/cover/test_template_metadata_refresh.py python-tests/cover/test_user_reported_publisher_typography.py -q
```

- [ ] **Step 5: Raise typography defaults**

Change `layout_publisher_info()` defaults to:

```python
heading_font_pt: float = 10.0
details_font_pt: float = 9.0
minimum_font_pt: float = 7.5
```

- [ ] **Step 6: Merge publisher text geometry adaptively**

In `refresh_template_metadata()`, precompute old and generated heading height.
For the heading, preserve old X/Y/width and use
`max(old.height_mm, generated.height_mm)`. For details, preserve X/width,
increase Y by positive heading growth, and use the larger height. Leave every
other managed element on the existing geometry-preservation path.

- [ ] **Step 7: Run tests and verify GREEN**

Run the Task 2 command and require all tests to pass.

- [ ] **Step 8: Commit**

```powershell
git add python/src/epub_a4_word/cover/publisher_info_layout.py python/src/epub_a4_word/cover/templates.py python-tests/cover/test_publisher_info_layout.py python-tests/cover/test_template_metadata_refresh.py python-tests/cover/test_user_reported_publisher_typography.py
git commit -m "fix: keep translator and publisher details readable"
```

### Task 3: Verify and publish v0.6.3

**Files:**
- Modify: `pyproject.toml`
- Modify: `python/src/epub_a4_word/__init__.py`
- Modify: `app/build.gradle.kts`
- Modify: `python-tests/test_android_bridge.py`

**Interfaces:**
- Consumes: existing tag-triggered `.github/workflows/release.yml`
- Produces: v0.6.3 Android and Windows assets

- [ ] **Step 1: Bump versions**

Set Python package/core to `0.6.3`, Android `versionCode` to `6`,
Android `versionName` to `0.6.3`, and the bridge assertion to `0.6.3`.

- [ ] **Step 2: Run all Python and Desktop tests**

```powershell
$env:PYTHONPATH="$pwd;python/src;app/src/main/python"
..\uv\uv.exe run pytest python-tests -q
$env:QT_QPA_PLATFORM='offscreen'
..\uv\uv.exe run pytest desktop/tests -q
```

- [ ] **Step 3: Build Android and Windows**

```powershell
..\gradle-8.13\bin\gradle.bat --no-daemon :app:testDebugUnitTest :app:assembleDebug
..\uv\uv.exe run python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec
..\uv\uv.exe run python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64
```

- [ ] **Step 4: Publish**

Commit the version bump, push the repair branch, open a PR against `main`, wait
for all three CI workflows, squash-merge, create annotated tag `v0.6.3`, and
push it.

- [ ] **Step 5: Verify release assets**

Require uploaded `EPUB2A4-Android.apk`,
`EPUB2A4-Windows-Portable-x64.zip`, and `SHA256SUMS.txt`.
