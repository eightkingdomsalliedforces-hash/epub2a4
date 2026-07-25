from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from epub_a4_word.cover.models import (
    CoverElement,
    CoverMetadata,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
    TrimSize,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word_desktop.cover.controller import CoverController
from epub_a4_word_desktop.cover.inspector import ElementInspector
from epub_a4_word_desktop.cover.layers_panel import LayersPanel
from epub_a4_word_desktop.cover.setup_panel import CoverSetupPanel
from epub_a4_word_desktop.pages.cover_page import CoverPage


def _project_json(tmp_path: Path) -> str:
    project = CoverProject(
        schema_version=1,
        source_file=str(tmp_path / "book.epub"),
        source_type="epub",
        metadata=CoverMetadata(title="範例書名", author="作者"),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path),
        elements=(
            CoverElement(
                id="front-title",
                kind=ElementKind.TEXT,
                region=Region.FRONT,
                transform=ElementTransform(120.0, 20.0, 80.0, 25.0),
                z_index=10,
                content={"text": "範例書名", "font_size_pt": 24.0},
            ),
        ),
    )
    return dumps_project(project)


def test_page_count_must_be_confirmed_before_create(qtbot, tmp_path: Path) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    panel.set_source(tmp_path / "book.epub")
    panel.page_count_spin.setValue(160)
    panel.page_count_confirmed.setChecked(False)

    assert not panel.create_button.isEnabled()
    panel.page_count_confirmed.setChecked(True)
    assert panel.create_button.isEnabled()


def test_paper_preset_updates_caliper_and_automatic_spine(qtbot) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    panel.page_count_spin.setValue(160)
    index = panel.paper_combo.findData(0.12)
    panel.paper_combo.setCurrentIndex(index)

    assert panel.caliper_spin.value() == pytest.approx(0.12)
    assert panel.automatic_spine_width_mm == pytest.approx(9.6)
    assert "9.600" in panel.spine_label.text()


def test_inspector_emits_exact_mm_patch(qtbot, tmp_path: Path) -> None:
    element = loads_project(_project_json(tmp_path)).elements_by_id["front-title"]
    inspector = ElementInspector()
    qtbot.addWidget(inspector)
    inspector.set_element(element)

    with qtbot.waitSignal(inspector.patch_requested) as signal:
        inspector.x_spin.setValue(12.75)
        inspector.x_spin.editingFinished.emit()

    assert signal.args == ["front-title", {"transform": {"x_mm": 12.75}}]


def test_layers_panel_emits_selection_deletion_order_and_visibility(
    qtbot, tmp_path: Path
) -> None:
    panel = LayersPanel()
    qtbot.addWidget(panel)
    panel.set_project(_project_json(tmp_path))
    selected: list[object] = []
    deleted: list[str] = []
    reordered: list[tuple[str, int]] = []
    visibility: list[tuple[str, bool]] = []
    panel.selection_changed.connect(selected.append)
    panel.delete_requested.connect(deleted.append)
    panel.z_order_requested.connect(lambda element_id, delta: reordered.append((element_id, delta)))
    panel.visibility_requested.connect(
        lambda element_id, visible: visibility.append((element_id, visible))
    )

    panel.list_widget.setCurrentRow(0)
    assert selected[-1] == "front-title"
    qtbot.mouseClick(panel.raise_button, Qt.MouseButton.LeftButton)
    assert reordered == [("front-title", 1)]

    item = panel.list_widget.currentItem()
    item.setCheckState(Qt.CheckState.Unchecked)
    assert visibility[-1] == ("front-title", False)

    qtbot.mouseClick(panel.delete_button, Qt.MouseButton.LeftButton)
    assert deleted == ["front-title"]


def test_conversion_payload_confirms_actual_page_count(qtbot, tmp_path: Path) -> None:
    page = CoverPage(controller=CoverController(working_dir=tmp_path, auto_preview=False))
    qtbot.addWidget(page)
    payload = {
        "source_path": str(tmp_path / "book.epub"),
        "page_count": 160,
        "trim_size_mm": {"width_mm": 105.0, "height_mm": 148.0},
    }

    page.open_from_conversion(payload)

    assert page.conversion_payload == payload
    assert page.setup_panel.page_count_spin.value() == 160
    assert page.setup_panel.page_count_confirmed.isChecked()
    assert page.setup_panel.source_path == Path(payload["source_path"])


def test_project_changes_update_canvas_layers_and_inspector(
    qtbot, tmp_path: Path
) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    page = CoverPage(controller=controller)
    qtbot.addWidget(page)
    project_json = _project_json(tmp_path)

    controller.replace_project(project_json, clear_history=True)
    assert "front-title" in page.canvas.items_by_id
    assert page.layers_panel.list_widget.count() == 1

    page.canvas.select_element("front-title")
    assert page.inspector.element_id == "front-title"

    page.canvas.element_transform_requested.emit(
        "front-title",
        {
            "x_mm": 14.0,
            "y_mm": 20.0,
            "width_mm": 80.0,
            "height_mm": 25.0,
            "rotation_deg": 0.0,
        },
    )
    assert (
        loads_project(controller.project_json)
        .elements_by_id["front-title"]
        .transform.x_mm
        == 14.0
    )


def test_add_text_button_creates_undoable_front_text(qtbot, tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    page = CoverPage(controller=controller)
    qtbot.addWidget(page)
    controller.replace_project(_project_json(tmp_path), clear_history=True)
    before_ids = set(loads_project(controller.project_json).elements_by_id)

    qtbot.mouseClick(page.assets_panel.add_text_button, Qt.MouseButton.LeftButton)

    project = loads_project(controller.project_json)
    new_ids = set(project.elements_by_id) - before_ids
    assert len(new_ids) == 1
    created = project.elements_by_id[new_ids.pop()]
    assert created.kind is ElementKind.TEXT
    assert created.region is Region.FRONT
    controller.undo()
    assert set(loads_project(controller.project_json).elements_by_id) == before_ids
