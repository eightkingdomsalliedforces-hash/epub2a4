from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from epub_a4_word_desktop.__main__ import main


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "packaging/windows/EPUB2A4.spec"
LAUNCHER = ROOT / "packaging/windows/launcher.py"
WORKFLOW = ROOT / ".github/workflows/windows-portable.yml"
ENTRY = ROOT / "python/src/epub_a4_word_desktop/__main__.py"


def test_portable_spec_is_onedir_gui_build() -> None:
    text = SPEC.read_text(encoding="utf-8")

    assert "EPUB2A4" in text
    assert "console=False" in text
    assert "COLLECT(" in text
    assert "onefile" not in text.lower()


def test_frozen_build_uses_package_safe_absolute_import_launcher() -> None:
    spec = SPEC.read_text(encoding="utf-8").replace("\\", "/")
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "packaging/windows/launcher.py" in spec
    assert "from epub_a4_word_desktop.__main__ import main" in launcher
    assert "from ." not in launcher


def test_windows_workflow_builds_smokes_and_archives_portable_app() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "windows-latest" in text
    assert 'python-version: "3.13"' in text
    assert "PyInstaller" in text or "pyinstaller" in text
    assert "--portable-smoke-test" in text
    assert "EPUB2A4-Windows-Portable-x64.zip" in text
    assert "Get-FileHash" in text
    assert "actions/upload-artifact" in text
    assert "test_single_page_blank_page_regression.py" in text
    assert "test_search_pipeline.py" in text
    assert "test_service.py" in text


def test_entry_supports_packaged_smoke_without_changing_legacy_order() -> None:
    text = ENTRY.read_text(encoding="utf-8")

    assert "--portable-smoke-test" in text
    legacy_position = text.index("--legacy-gui")
    widgets_position = text.find("PySide6.QtWidgets")
    assert widgets_position == -1 or legacy_position < widgets_position


def test_portable_smoke_flag_uses_dedicated_short_lived_runner() -> None:
    with patch(
        "epub_a4_word_desktop.__main__.run_portable_smoke",
        return_value=0,
    ) as run:
        assert main(["--portable-smoke-test"]) == 0
        run.assert_called_once_with([])


def test_workflow_runs_packaged_executable_not_only_python_sources() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").replace("\\", "/")

    assert "EPUB2A4.exe" in text
    assert "dist/EPUB2A4-Windows-Portable-x64" in text
    assert "verify_windows_portable.py" in text
    assert "WaitForExit(30000)" in text
    assert "cancel-in-progress: true" in text


def test_new_safe_export_modules_are_in_collected_package_trees() -> None:
    required = (
        ROOT / "python/src/epub_a4_word/text_metrics.py",
        ROOT / "python/src/epub_a4_word/cover/export_plan.py",
        ROOT / "python/src/epub_a4_word_desktop/cover/alias_decision_row.py",
        ROOT / "python/src/epub_a4_word_desktop/cover/export_preview_dialog.py",
    )

    assert all(path.is_file() for path in required)
    spec = SPEC.read_text(encoding="utf-8")
    assert 'collect_all(package_name)' in spec
    assert '"epub_a4_word"' in spec
    assert '"epub_a4_word_desktop"' in spec
