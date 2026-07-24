# Cover Search, Credentials, and Portable Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in cover search with multiple candidates, secure local credential handling, validated image download/cache, and portable Windows/macOS/Linux release artifacts while preserving independent Android packaging.

**Architecture:** Implement provider request/response normalization in the shared Python package so Android and desktop interpret Google Books, Open Library, and Google Custom Search identically. Platform layers own credentials and user interaction, pass credentials only for one request, display source/use-right warnings, and copy a selected image into the current cover project before editing.

**Tech Stack:** Python 3.13 stdlib HTTPS/JSON, Pillow, pytest; Google Books API, Open Library APIs, Google Custom Search JSON API; Android Keystore AES-GCM, Compose, Coil 3.5.0; desktop keyring 25.7.0, platformdirs 4.10.1; PyInstaller, AppImage tooling, GitHub Actions.

## Global Constraints

- This plan starts after the shared core, desktop editor, and Android editor plans pass.
- Search order: ISBN in public book databases, title+author in public book databases, then optional general image search.
- Public providers: Google Books and Open Library.
- General image provider in the first release: Google Custom Search image mode.
- General search requires a user-supplied API Key and Search Engine ID; no shared credential may appear in source, APK, desktop package, CI logs, fixtures, or crash output.
- Search shows multiple candidates and never auto-selects the first result.
- General image search occurs only after the user explicitly switches to it and presses Search.
- All requests use HTTPS and bounded timeouts.
- Source EPUB/DOCX/PDF files are never uploaded; requests contain only ISBN, title, author, locale, or user-entered keywords.
- Search failure never disables local/embedded cover creation.
- Selected image downloads are limited to 50 MiB and 20,000 × 20,000 decoded pixels.
- UI displays source page and `授權狀態未確認；使用者需自行確認使用權` unless a provider supplies an explicit rights value.
- Android network permission is added only in this plan.
- Desktop packages are portable and perform no version check or automatic update.
- Standard desktop mode stores settings in platform user-data directories; portable mode activates with `portable.flag` and writes beneath `data/`.

---

## Part 3: Tasks 9–11

### Task 9: Finalize portable mode and explicitly disable update checks

**Files:**
- Create: `python/src/epub_a4_word_desktop/settings/runtime.py`
- Create: `python/src/epub_a4_word_desktop/settings/preferences.py`
- Modify: `python/src/epub_a4_word_desktop/app.py`
- Modify: `python/src/epub_a4_word_desktop/main_window.py`
- Create: `desktop/tests/test_runtime_settings.py`
- Modify: `README.md`

**Interfaces:**
- Runtime settings include cache size, last directory, guide visibility, and search safety; never project geometry.
- No function, timer, request, menu item, or background job checks for application updates.

- [ ] **Step 1: Add failing portable preference tests**

```python
def test_preferences_write_to_selected_config_dir(tmp_path):
    paths = AppPaths(config_dir=tmp_path / "config", cache_dir=tmp_path / "cache", data_dir=tmp_path / "data", portable=True)
    store = PreferenceStore(paths)
    store.save(UserPreferences(last_directory="/books", safe_search=True))
    assert (tmp_path / "config/preferences.json").is_file()


def test_runtime_has_no_update_service_import():
    import epub_a4_word_desktop
    modules = {name for name in sys.modules if name.startswith("epub_a4_word_desktop")}
    assert not any("update" in name.lower() for name in modules)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_runtime_settings.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement atomic preferences and cache cleanup**

Preferences JSON uses schema version `1`, atomic replace, and safe defaults after corrupt JSON is renamed to `.corrupt-<timestamp>`. Enforce configured cache limit on startup and after downloads.

```python
DEFAULT_PREFERENCES = {"schema_version": 1, "cache_limit_mib": 256}


def load_preferences(path: Path) -> dict[str, object]:
    if not path.exists():
        return dict(DEFAULT_PREFERENCES)
    try:
        value = json.loads(path.read_text("utf-8"))
        if value.get("schema_version") != 1:
            raise ValueError("unsupported schema")
        return {**DEFAULT_PREFERENCES, **value}
    except (OSError, ValueError, json.JSONDecodeError):
        corrupt = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        path.replace(corrupt)
        return dict(DEFAULT_PREFERENCES)


def save_preferences(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")
    os.replace(temporary, path)


def apply_cache_limit(cache: ImageCache, preferences: Mapping[str, object]) -> None:
    cache.max_bytes = int(preferences["cache_limit_mib"]) * 1024 * 1024
    cache.enforce_limit()
```

- [ ] **Step 4: Add portable-mode UI indicator**

Status bar displays `可攜模式` or `標準模式`. Help/About states updates are manual and directs the user to download a new package; it does not query a URL.

```python
def apply_runtime_mode(self, paths: RuntimePaths) -> None:
    label = "可攜模式" if paths.mode == "portable" else "標準模式"
    self.runtime_mode_label.setText(label)
    self.statusBar().addPermanentWidget(self.runtime_mode_label)


def show_about(self) -> None:
    QMessageBox.information(
        self,
        "關於 EPUB2A4",
        "本程式不會自動檢查更新。取得新版時，請手動下載新的免安裝包並替換舊版。",
    )
```

```python
def test_desktop_has_no_update_module_or_scheduler():
    root = Path("python/src/epub_a4_word_desktop")
    forbidden_names = {"updater.py", "update_checker.py", "auto_update.py"}
    assert not any(path.name in forbidden_names for path in root.rglob("*.py"))
    source_text = "\n".join(path.read_text("utf-8") for path in root.rglob("*.py"))
    for symbol in ("check_for_updates", "schedule_update_check", "download_update"):
        assert symbol not in source_text
```

- [ ] **Step 5: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_runtime_settings.py -q
git add python/src/epub_a4_word_desktop/settings \
  python/src/epub_a4_word_desktop/app.py python/src/epub_a4_word_desktop/main_window.py \
  desktop/tests/test_runtime_settings.py README.md
git commit -m "feat: finalize desktop portable runtime settings"
```

Expected: PASS.

---

### Task 10: Build portable Windows, macOS, and Linux artifacts

**Files:**
- Create: `packaging/desktop/epub2a4.spec`
- Create: `packaging/desktop/runtime_hook.py`
- Create: `packaging/windows/build-portable.ps1`
- Create: `packaging/macos/build-portable.sh`
- Create: `packaging/linux/build-appimage.sh`
- Create: `packaging/linux/EPUB2A4.desktop`
- Create: `packaging/linux/AppRun`
- Create: `desktop/tests/test_packaging_metadata.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Windows output: `dist/EPUB2A4-Windows-portable.zip` containing an onedir application.
- macOS output: `dist/EPUB2A4-macOS.app.zip`.
- Linux output: `dist/EPUB2A4-Linux-x86_64.AppImage`.
- Each artifact contains `licenses/`, local templates, Qt plugins actually used, and no API credential file.

- [ ] **Step 1: Write failing packaging metadata tests**

```python
def test_spec_includes_shared_templates_and_excludes_credentials():
    text = Path("packaging/desktop/epub2a4.spec").read_text("utf-8")
    assert "epub_a4_word/cover" in text
    assert "credentials.json" not in text
    assert "keyring" in text


def test_portable_artifact_names_are_stable():
    assert windows_artifact_name() == "EPUB2A4-Windows-portable.zip"
    assert macos_artifact_name() == "EPUB2A4-macOS.app.zip"
    assert linux_artifact_name() == "EPUB2A4-Linux-x86_64.AppImage"
```

- [ ] **Step 2: Run tests and verify missing files fail**

```bash
python3.13 -m pytest desktop/tests/test_packaging_metadata.py -q
```

Expected: FAIL because packaging files do not exist.

- [ ] **Step 3: Add packaging dependency and PyInstaller spec**

Add desktop build extra:

```toml
build-desktop = ["PyInstaller>=6.12,<7"]
```

Spec requirements:

- entry `python/src/epub_a4_word_desktop/__main__.py`;
- source path `python/src`;
- collect PySide6 platform/image plugins, keyring backends, Pillow plugins, templates, and license files;
- exclude test modules, tkinter from the default executable only if the separate legacy launch path is still bundled and tested; because `--legacy-gui` is required, include Tcl/Tk runtime in this one release;
- use onedir/standalone mode, not onefile extraction.

- [ ] **Step 4: Implement native build scripts**

Windows PowerShell:

```powershell
python -m PyInstaller --noconfirm packaging/desktop/epub2a4.spec
Compress-Archive -Path dist/EPUB2A4/* -DestinationPath dist/EPUB2A4-Windows-portable.zip -Force
```

macOS:

```bash
python3 -m PyInstaller --noconfirm packaging/desktop/epub2a4.spec
ditto -c -k --sequesterRsrc --keepParent dist/EPUB2A4.app dist/EPUB2A4-macOS.app.zip
```

Linux script creates an AppDir from PyInstaller onedir output, copies `AppRun`, desktop file, icon, then calls `appimagetool` with `ARCH=x86_64`.

- [ ] **Step 5: Add artifact credential scan**

Each script unpacks/scans strings and file names for known test secrets and patterns `AIza`, `search_engine_id`, `credentials.json`. Fail build if found outside source-code labels/help text; use a generated canary secret in packaging tests to prove the scanner catches leaks.

```python
FORBIDDEN_PATTERNS = (
    re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(rb"CANARY_API_KEY_[0-9A-F]{16}"),
)
FORBIDDEN_NAMES = {"credentials.json", "google-api-key.txt"}


def scan_artifact(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if path.name.casefold() in FORBIDDEN_NAMES:
            findings.append(str(path))
        if not path.is_file() or path.stat().st_size > 200 * 1024 * 1024:
            continue
        data = path.read_bytes()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(data):
                findings.append(f"{path}: {pattern.pattern!r}")
    return findings


def assert_artifact_has_no_credentials(root: Path) -> None:
    findings = scan_artifact(root)
    if findings:
        raise SystemExit("Credential material found:\n" + "\n".join(findings))
```

- [ ] **Step 6: Run packaging metadata tests and commit**

```bash
python3.13 -m pytest desktop/tests/test_packaging_metadata.py -q
git add packaging pyproject.toml desktop/tests/test_packaging_metadata.py
git commit -m "build: add portable desktop packaging scripts"
```

Expected: PASS.

---

### Task 11: Add CI matrix, live opt-in checks, and final cross-platform acceptance

**Files:**
- Create: `.github/workflows/desktop-release.yml`
- Modify: `.github/workflows/android.yml`
- Create: `python-tests/cover/search/test_live_providers.py`
- Create: `scripts/verify_release_artifact.py`
- Modify: `README.md`
- Modify: `BUILDING.md`
- Modify: `BUILD_STATUS.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Desktop workflow matrix: `windows-latest`, `macos-latest`, `ubuntu-latest`.
- Live provider tests run only on manual workflow dispatch when required secrets exist.
- Android workflow verifies INTERNET exists after this plan and no broad storage permissions exist.

- [ ] **Step 1: Add opt-in live provider tests**

```python
@pytest.mark.skipif(not os.getenv("GOOGLE_CSE_API_KEY"), reason="live credential not configured")
def test_live_google_custom_search_returns_https_candidates():
    provider = GoogleCustomSearchProvider(JsonHttpClient())
    result = provider.search(
        CoverSearchRequest(query="public domain book cover", max_results=2),
        ProviderCredential(os.environ["GOOGLE_CSE_API_KEY"], os.environ["GOOGLE_CSE_CX"]),
    )
    assert result.candidates
    assert all(c.image_url.startswith("https://") for c in result.candidates)
```

Live tests never print credential values or full request URLs.

- [ ] **Step 2: Implement desktop CI matrix**

For every runner:

```text
checkout
setup Python 3.13
pip install -e .[desktop,test,build-desktop]
run Python and desktop tests offscreen where applicable
build native portable artifact
run artifact verifier
upload artifact
```

Linux additionally installs FUSE/AppImage build requirements; macOS verifies `.app` launches with a smoke argument; Windows starts the executable with `--smoke-test`.

```yaml
# .github/workflows/desktop-release.yml
name: Desktop portable builds

on:
  workflow_dispatch:
  push:
    branches: [main]

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            artifact: EPUB2A4-Windows-portable.zip
            build: powershell -File packaging/windows/build-portable.ps1
          - os: macos-latest
            artifact: EPUB2A4-macOS.app.zip
            build: bash packaging/macos/build-portable.sh
          - os: ubuntu-24.04
            artifact: EPUB2A4-Linux-x86_64.AppImage
            build: bash packaging/linux/build-appimage.sh
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install Linux build packages
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y libfuse2 patchelf
      - name: Install project
        run: python -m pip install -e ".[desktop,test,build-desktop]"
      - name: Test shared and desktop code
        env:
          QT_QPA_PLATFORM: offscreen
        run: python -m pytest python-tests desktop/tests -q
      - name: Build portable artifact
        run: ${{ matrix.build }}
      - name: Verify portable artifact
        run: python scripts/verify_release_artifact.py "dist/${{ matrix.artifact }}"
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: dist/${{ matrix.artifact }}
```

Create platform-specific smoke steps after the artifact verifier:

```yaml
      - name: Windows smoke
        if: runner.os == 'Windows'
        run: .\dist\EPUB2A4\EPUB2A4.exe --smoke-test
      - name: macOS smoke
        if: runner.os == 'macOS'
        run: ./dist/EPUB2A4.app/Contents/MacOS/EPUB2A4 --smoke-test
      - name: Linux smoke
        if: runner.os == 'Linux'
        run: chmod +x dist/EPUB2A4-Linux-x86_64.AppImage && dist/EPUB2A4-Linux-x86_64.AppImage --appimage-extract-and-run --smoke-test
```

- [ ] **Step 3: Extend application entry with smoke mode**

Add `--smoke-test` which initializes paths, imports Qt/core/search modules, creates and closes `MainWindow` offscreen, prints `EPUB2A4 smoke: PASS`, and exits `0`. It does not open network connections.

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-gui", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    return parser


def run_smoke_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    paths = resolve_runtime_paths(Path(sys.executable).resolve().parent)
    from epub_a4_word.cover.search.aggregate import search_public_candidates
    from epub_a4_word_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(paths=paths)
    window.show()
    app.processEvents()
    window.close()
    print("EPUB2A4 smoke: PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke_test:
        return run_smoke_test()
    if args.legacy_gui:
        return run_legacy_gui()
    return run_qt_app([])
```

- [ ] **Step 4: Verify Android manifest and APK**

```bash
apkanalyzer manifest permissions app-debug.apk
```

Expected permissions include `android.permission.INTERNET`; they do not include `MANAGE_EXTERNAL_STORAGE`, `READ_EXTERNAL_STORAGE`, or `WRITE_EXTERNAL_STORAGE`.

- [ ] **Step 5: Run final local gates**

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests -q
gradle --no-daemon testDebugUnitTest assembleDebug
python3.13 scripts/verify_project.py
```

Expected: zero failures.

- [ ] **Step 6: Update documentation and commit**

Document search order, credential setup, source/use-right warning, offline fallback, portable mode, manual updates, artifact formats, and exact build commands.

```bash
git add .github/workflows python-tests/cover/search/test_live_providers.py \
  scripts/verify_release_artifact.py README.md BUILDING.md BUILD_STATUS.md CHANGELOG.md
git commit -m "ci: verify cover search and portable releases"
```
