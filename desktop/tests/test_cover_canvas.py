from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QRectF

from epub_a4_word.cover.geometry import calculate_layout
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
from epub_a4_word_desktop.cover.canvas import CoverCanvas
from epub_a4_word_desktop.cover.items import CoverImageItem, CoverTextItem


def _project_json(tmp_path: Path) -> str:
    image_path = tmp_path / "cover.png"
    Image.new("RGB", (60, 90), "white").save(image_path)
    project = CoverProject(
        schema_version=1,
        source_file=str(tmp_path / "book.epub"),
        source_type="epub",
        metadata=CoverMetadata(title="範例書名", author="範例作者"),
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
                id="front-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(116.0, 3.0, 105.0, 148.0),
                z_index=0,
                content={"path": str(image_path), "fit": "cover"},
            ),
            CoverElement(
                id="front-title",
                kind=ElementKind.TEXT,
                region=Region.FRONT,
                transform=ElementTransform(124.0, 18.0, 80.0, 25.0),
                z_index=10,
                content={"text": "範例書名", "font_size_pt": 24.0},
            ),
        ),
    )
    return dumps_project(project)


def test_scene_rect_uses_layout_millimetres(qtbot, tmp_path: Path) -> None:
    project_json = _project_json(tmp_path)
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(project_json)
    layout = calculate_layout(loads_project(project_json))

    assert canvas.scene().sceneRect().x() == pytest.approx(0.0)
    assert canvas.scene().sceneRect().y() == pytest.approx(0.0)
    assert canvas.scene().sceneRect().width() == pytest.approx(layout.bleed_rect.width_mm)
    assert canvas.scene().sceneRect().height() == pytest.approx(layout.bleed_rect.height_mm)


def test_project_elements_create_selectable_image_and_text_items(
    qtbot, tmp_path: Path
) -> None:
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(_project_json(tmp_path))

    assert isinstance(canvas.items_by_id["front-image"], CoverImageItem)
    assert isinstance(canvas.items_by_id["front-title"], CoverTextItem)
    assert canvas.items_by_id["front-image"].element_id == "front-image"
    assert canvas.items_by_id["front-title"].element_id == "front-title"


def test_drag_commit_emits_exact_mm_transform(qtbot, tmp_path: Path) -> None:
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(_project_json(tmp_path))

    with qtbot.waitSignal(canvas.element_transform_requested) as signal:
        canvas._commit_item_transform(
            "front-title",
            QRectF(12.5, 20.0, 80.0, 25.0),
            7.5,
        )

    assert signal.args == [
        "front-title",
        {
            "x_mm": 12.5,
            "y_mm": 20.0,
            "width_mm": 80.0,
            "height_mm": 25.0,
            "rotation_deg": 7.5,
        },
    ]


def test_select_element_emits_identifier_and_none(qtbot, tmp_path: Path) -> None:
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(_project_json(tmp_path))
    selected: list[object] = []
    canvas.element_selected.connect(selected.append)

    canvas.select_element("front-title")
    assert selected[-1] == "front-title"
    assert canvas.items_by_id["front-title"].isSelected()

    canvas.select_element(None)
    assert selected[-1] is None


def test_guides_are_locked_and_not_serialized(qtbot, tmp_path: Path) -> None:
    project_json = _project_json(tmp_path)
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(project_json)

    assert canvas.guide_layer.items
    for group in canvas.guide_layer.items.values():
        assert all(not item.flags().value & 2 for item in group)
    assert loads_project(project_json).elements == loads_project(canvas.project_json).elements


def test_zoom_is_view_only_and_clamped(qtbot, tmp_path: Path) -> None:
    project_json = _project_json(tmp_path)
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(project_json)
    pixels_per_mm = 96.0 / 25.4

    canvas.set_zoom(100.0)
    assert canvas.transform().m11() == pytest.approx(pixels_per_mm * 8.0)
    canvas.set_zoom(0.001)
    assert canvas.transform().m11() == pytest.approx(pixels_per_mm * 0.10)
    assert canvas.project_json == project_json
