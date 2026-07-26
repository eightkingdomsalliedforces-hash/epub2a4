from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from epub_a4_word.cover.models import CoverMetadata, CoverProject, ImageMode, TrimSize
from epub_a4_word.cover.project_io import dumps_project
from epub_a4_word_desktop.cover.export_preview_dialog import ExportPreviewDialog
from epub_a4_word_desktop.cover.export_worker import export_paths


def _project_json(tmp_path: Path) -> str:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return dumps_project(
        CoverProject(
            schema_version=1,
            source_file=str(source),
            source_type="epub",
            metadata=CoverMetadata(title="範例書", author="作者"),
            trim_size=TrimSize(148.0, 210.0),
            page_count=160,
            paper_caliper_mm=0.10,
            manual_spine_width_mm=None,
            bleed_mm=3.0,
            overlap_mm=5.0,
            image_mode=ImageMode.FRONT_ONLY,
            working_dir=str(tmp_path),
        )
    )


def test_preview_lists_two_a4_pages_overlap_and_three_files(qtbot, tmp_path: Path) -> None:
    project_json = _project_json(tmp_path)
    paths = export_paths(project_json, tmp_path / "exports")
    dialog = ExportPreviewDialog(project_json, paths, 200)
    qtbot.addWidget(dialog)

    assert "2 頁" in dialog.summary_label.text()
    assert "10.0 mm" in dialog.summary_label.text()
    assert [label.text() for label in dialog.page_labels] == [
        "第 1 頁／2：封底側",
        "第 2 頁／2：正面側",
    ]
    assert paths.original_pdf.name in dialog.files_label.text()
    assert paths.print_pdf.name in dialog.files_label.text()
    assert paths.print_docx.name in dialog.files_label.text()


def test_blank_back_requires_explicit_continue(qtbot, tmp_path: Path) -> None:
    project_json = _project_json(tmp_path)
    dialog = ExportPreviewDialog(
        project_json,
        export_paths(project_json, tmp_path / "exports"),
        200,
    )
    qtbot.addWidget(dialog)

    assert dialog.blank_back_warning.isVisibleTo(dialog)
    assert not dialog.confirmed_export
    assert not dialog.export_button.isEnabled()

    qtbot.mouseClick(dialog.continue_blank_button, Qt.MouseButton.LeftButton)

    assert dialog.confirmed_export
    assert dialog.export_button.isEnabled()
