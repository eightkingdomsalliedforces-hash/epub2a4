from __future__ import annotations

from pathlib import Path

from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word_desktop.cover.controller import CoverController
from epub_a4_word_desktop.pages.cover_page import TemplatePanel


def _project_json(tmp_path: Path) -> str:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return dumps_project(
        CoverProject(
            schema_version=1,
            source_file=str(source),
            source_type="epub",
            metadata=CoverMetadata(title="模板測試", author="epub2a4"),
            trim_size=TrimSize(105.0, 148.0),
            page_count=160,
            paper_caliper_mm=0.10,
            manual_spine_width_mm=None,
            bleed_mm=3.0,
            overlap_mm=5.0,
            image_mode=ImageMode.FRONT_ONLY,
            working_dir=str(tmp_path),
        )
    )


def test_all_template_panel_options_apply_through_controller(qtbot, tmp_path: Path) -> None:
    panel = TemplatePanel()
    qtbot.addWidget(panel)
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    original = _project_json(tmp_path)

    for index in range(panel.combo.count()):
        controller.replace_project(original, clear_history=True)
        template_id = str(panel.combo.itemData(index))
        controller.apply_template(template_id)
        project = loads_project(controller.project_json)
        if template_id == "minimal":
            assert project.elements == ()
        else:
            assert project.elements
