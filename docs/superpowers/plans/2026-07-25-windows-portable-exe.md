# Windows Portable EXE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a Windows x64 portable ZIP containing a directly runnable `EPUB2A4.exe` with all Python and PySide6 dependencies bundled.

**Architecture:** Add a testable internal portable-smoke command to the existing desktop entry point, describe the onedir build in one PyInstaller spec, and run a dedicated Windows GitHub Actions job which tests source code, builds the executable, runs the packaged executable offscreen, archives the complete directory, and publishes ZIP plus SHA-256 artifacts. The packaging layer delegates to the existing desktop application and shared core; it does not duplicate conversion or cover logic.

**Tech Stack:** Python 3.13, PySide6 6.11.1, PyInstaller 6.x, pytest, GitHub Actions `windows-latest`, PowerShell.

## Global Constraints

- Output is an onedir portable ZIP, not a onefile executable and not an installer.
- Artifact file name is exactly `EPUB2A4-Windows-Portable-x64.zip`.
- Executable file name is exactly `EPUB2A4.exe`.
- The default GUI remains PySide6.
- `--legacy-gui` remains available and must still branch before importing PySide6 Widgets.
- The packaged application must include conversion and cover-editor functionality through the existing shared core.
- The packaged executable must be launched successfully in GitHub Actions with `QT_QPA_PLATFORM=offscreen`.
- Python 3.13 and PySide6 6.11.1 remain fixed.
- No Windows installer, registry changes, auto-update, code signing, Android UI, or search implementation is included.
- The draft feature branch remains unmerged.

---

### Task 1: Define portable packaging and smoke-test contracts

**Files:**
- Create: `desktop/tests/test_windows_portable_packaging.py`
- Modify: `python/src/epub_a4_word_desktop/__main__.py`
- Modify or create as required by the existing entry architecture: `python/src/epub_a4_word_desktop/app.py`

**Interfaces:**
- Consumes: existing `epub_a4_word_desktop.__main__.main(argv: list[str] | None = None) -> int` or the closest existing command entry.
- Produces: internal CLI option `--portable-smoke-test` returning process exit code `0` after creating and closing the PySide6 main window.
- Preserves: `--legacy-gui` dispatch before any `PySide6.QtWidgets` import.

- [ ] **Step 1: Write the failing packaging contract tests**

Create `desktop/tests/test_windows_portable_packaging.py` with tests which read repository files and inspect the entry module. The tests must assert:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "packaging/windows/EPUB2A4.spec"
WORKFLOW = ROOT / ".github/workflows/windows-portable.yml"
ENTRY = ROOT / "python/src/epub_a4_word_desktop/__main__.py"


def test_portable_spec_is_onedir_gui_build():
    text = SPEC.read_text(encoding="utf-8")
    assert "name='EPUB2A4'" in text or 'name="EPUB2A4"' in text
    assert "console=False" in text
    assert "COLLECT(" in text
    assert "onefile" not in text.lower()


def test_windows_workflow_builds_smokes_and_archives_portable_app():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "windows-latest" in text
    assert 'python-version: "3.13"' in text
    assert "PyInstaller" in text or "pyinstaller" in text
    assert "--portable-smoke-test" in text
    assert "EPUB2A4-Windows-Portable-x64.zip" in text
    assert "Get-FileHash" in text


def test_entry_supports_packaged_smoke_without_changing_legacy_order():
    text = ENTRY.read_text(encoding="utf-8")
    assert "--portable-smoke-test" in text
    legacy_position = text.index("--legacy-gui")
    widgets_position = text.find("PySide6.QtWidgets")
    assert widgets_position == -1 or legacy_position < widgets_position
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest \
  desktop/tests/test_windows_portable_packaging.py -q
```

Expected: failure because `packaging/windows/EPUB2A4.spec`, `.github/workflows/windows-portable.yml`, and `--portable-smoke-test` do not exist.

- [ ] **Step 3: Add the minimal portable-smoke entry behavior**

Keep argument parsing free of `PySide6.QtWidgets` imports. After handling `--legacy-gui`, dispatch `--portable-smoke-test` to a helper which imports Qt lazily, creates the existing application and main window, shows it using offscreen mode when configured, processes events, confirms HOME/CONVERTER/COVER routes are registered using the existing navigation API, closes the window, and returns `0`.

The helper must not start a permanent event loop and must not create a second implementation of `MainWindow`.

- [ ] **Step 4: Run focused entry tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=python/src:app/src/main/python \
python3.13 -m pytest desktop/tests/test_entrypoint.py \
  desktop/tests/test_windows_portable_packaging.py -q
```

Expected: packaging file assertions remain RED, while entrypoint smoke and legacy-order assertions pass.

- [ ] **Step 5: Commit the Task 1 RED-to-partial-GREEN checkpoint**

```bash
git add desktop/tests/test_windows_portable_packaging.py \
  python/src/epub_a4_word_desktop

git commit -m "test: define Windows portable desktop contract"
```

---

### Task 2: Build the PyInstaller onedir bundle and Windows artifact workflow

**Files:**
- Create: `packaging/windows/EPUB2A4.spec`
- Create: `.github/workflows/windows-portable.yml`
- Create: `scripts/verify_windows_portable.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `BUILD_STATUS.md`
- Test: `desktop/tests/test_windows_portable_packaging.py`

**Interfaces:**
- Consumes: `python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec`.
- Produces: `dist/EPUB2A4-Windows-Portable-x64/EPUB2A4.exe` plus `_internal` runtime files.
- Produces: `EPUB2A4-Windows-Portable-x64.zip` and `.sha256`.
- Verification command: `python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64`.

- [ ] **Step 1: Add the PyInstaller packaging dependency**

Add a single optional dependency group without duplicating setuptools configuration:

```toml
portable = [
  "PyInstaller>=6.14,<7",
]
```

The existing `desktop` and `test` groups remain unchanged.

- [ ] **Step 2: Implement the PyInstaller spec**

Create `packaging/windows/EPUB2A4.spec` using PyInstaller hook utilities:

```python
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

hiddenimports = []
datas = []
binaries = []

for package in (
    "epub_a4_word",
    "epub_a4_word_desktop",
    "PIL",
    "bs4",
    "docx",
    "pypdf",
    "keyring",
    "platformdirs",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += collect_submodules("lxml")
```

Use an `Analysis` entry of `python/src/epub_a4_word_desktop/__main__.py`, set `pathex` to `python/src` and `app/src/main/python`, use `EXE(..., name="EPUB2A4", console=False)`, and finish with `COLLECT` named `EPUB2A4-Windows-Portable-x64`.

Do not add source tests or repository metadata as data files.

- [ ] **Step 3: Implement portable-directory validation**

Create `scripts/verify_windows_portable.py` which accepts one directory argument and fails unless all conditions hold:

```python
required = [
    root / "EPUB2A4.exe",
    root / "_internal",
]
```

It must recursively locate at least one Qt platform plugin named `qwindows.dll`, reject `.git`, `__pycache__`, `.pytest_cache`, `.pyc`, and source test directories, ensure the total package size is greater than zero, and print a compact JSON summary containing executable path, file count, and total bytes.

- [ ] **Step 4: Implement the Windows GitHub Actions workflow**

Create `.github/workflows/windows-portable.yml` with `workflow_dispatch`, feature-branch push, and pull-request triggers. Use `windows-latest`, Python 3.13, and these gates in order:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test,desktop,portable]"
python -m pytest python-tests desktop/tests -q --junitxml=windows-portable-tests.xml
$env:QT_QPA_PLATFORM = "offscreen"
python scripts/desktop_smoke.py --offscreen
python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec
python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64
dist/EPUB2A4-Windows-Portable-x64/EPUB2A4.exe --portable-smoke-test
Compress-Archive -Path dist/EPUB2A4-Windows-Portable-x64 -DestinationPath EPUB2A4-Windows-Portable-x64.zip
(Get-FileHash EPUB2A4-Windows-Portable-x64.zip -Algorithm SHA256).Hash.ToLower() + "  EPUB2A4-Windows-Portable-x64.zip" | Set-Content EPUB2A4-Windows-Portable-x64.zip.sha256
```

Upload the ZIP and SHA file as artifact `EPUB2A4-Windows-Portable-x64`; upload `windows-portable-tests.xml`, PyInstaller warnings, and verification output with `if: always()`.

- [ ] **Step 5: Complete the focused tests locally or through the existing desktop matrix**

Run:

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest \
  desktop/tests/test_windows_portable_packaging.py -q
```

Expected: PASS.

- [ ] **Step 6: Run all source gates**

Run:

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests desktop/tests -q
PYTHONPATH=python/src:app/src/main/python python3.13 -m compileall -q python/src app/src/main/python scripts
python3.13 scripts/verify_project.py
```

Expected: zero failures and project verification PASS.

- [ ] **Step 7: Update user documentation**

Document that Windows users can download the Actions artifact, extract all files, and double-click `EPUB2A4.exe`. State that moving only the EXE or deleting `_internal` breaks the portable application, and that the unsigned first release may trigger SmartScreen.

- [ ] **Step 8: Commit the implementation**

```bash
git add packaging/windows/EPUB2A4.spec \
  .github/workflows/windows-portable.yml \
  scripts/verify_windows_portable.py \
  pyproject.toml README.md BUILD_STATUS.md \
  desktop/tests/test_windows_portable_packaging.py

git commit -m "build: publish Windows portable desktop executable"
```

- [ ] **Step 9: Verify the real Windows artifact GREEN**

Wait for the `Windows portable EXE` workflow. Require all steps to succeed, including the packaged `EPUB2A4.exe --portable-smoke-test`. Download the uploaded artifact and verify the ZIP can be opened, contains the top-level portable directory and executable, and its calculated SHA-256 matches the `.sha256` file.
