from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "packaging/windows/EPUB2A4.spec"
WORKFLOW = ROOT / ".github/workflows/windows-portable.yml"
ENTRY = ROOT / "python/src/epub_a4_word_desktop/__main__.py"


def test_portable_spec_is_onedir_gui_build() -> None:
    text = SPEC.read_text(encoding="utf-8")

    assert "EPUB2A4" in text
    assert "console=False" in text
    assert "COLLECT(" in text
    assert "onefile" not in text.lower()


def test_windows_workflow_builds_smokes_and_archives_portable_app() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "windows-latest" in text
    assert 'python-version: "3.13"' in text
    assert "PyInstaller" in text or "pyinstaller" in text
    assert "--portable-smoke-test" in text
    assert "EPUB2A4-Windows-Portable-x64.zip" in text
    assert "Get-FileHash" in text
    assert "actions/upload-artifact" in text


def test_entry_supports_packaged_smoke_without_changing_legacy_order() -> None:
    text = ENTRY.read_text(encoding="utf-8")

    assert "--portable-smoke-test" in text
    legacy_position = text.index("--legacy-gui")
    widgets_position = text.find("PySide6.QtWidgets")
    assert widgets_position == -1 or legacy_position < widgets_position


def test_workflow_runs_packaged_executable_not_only_python_sources() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").replace("\\", "/")

    assert "EPUB2A4.exe" in text
    assert "dist/EPUB2A4-Windows-Portable-x64" in text
    assert "verify_windows_portable.py" in text
