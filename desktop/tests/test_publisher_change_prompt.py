from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.project_io import dumps_project
from epub_a4_word_desktop.cover.controller import CoverController
from epub_a4_word_desktop.pages.cover_page import CoverPage


def _project(tmp_path: Path) -> CoverProject:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="Example", publisher="Old Publisher"),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path),
    )


def test_changing_publisher_can_update_text_and_search_replacement_logo(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    page = CoverPage(controller=controller)
    qtbot.addWidget(page)
    controller.replace_project(dumps_project(_project(tmp_path)), clear_history=True)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    searches: list[str] = []
    monkeypatch.setattr(page, "_search_publisher_logo", searches.append)

    page.publisher_metadata_panel.publisher_edit.setText("New Publisher")
    page._publisher_update_timer.stop()
    page._commit_publisher_metadata()

    assert searches == ["New Publisher"]
