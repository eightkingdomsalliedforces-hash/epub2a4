from __future__ import annotations

from pathlib import Path

import pytest

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
from epub_a4_word_desktop.cover.controller import CoverController


def _text_element(
    element_id: str,
    transform: ElementTransform,
    *,
    role: str,
    font_size_pt: float,
) -> CoverElement:
    return CoverElement(
        id=element_id,
        kind=ElementKind.TEXT,
        region=Region.BACK,
        transform=transform,
        z_index=20,
        content={
            "text": element_id,
            "font_size_pt": font_size_pt,
            "line_spacing_mm": 3.0,
            "group_id": "publisher-info-stack",
            "layout_role": role,
        },
    )


def _project(tmp_path: Path) -> CoverProject:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="書名"),
        trim_size=TrimSize(128.0, 182.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path),
        elements=(
            _text_element(
                "back-publisher-heading",
                ElementTransform(10.0, 10.0, 20.0, 4.0),
                role="heading",
                font_size_pt=7.5,
            ),
            _text_element(
                "back-publisher-details",
                ElementTransform(10.0, 15.0, 20.0, 8.0),
                role="details",
                font_size_pt=6.5,
            ),
            CoverElement(
                id="unrelated",
                kind=ElementKind.TEXT,
                region=Region.FRONT,
                transform=ElementTransform(60.0, 60.0, 20.0, 10.0),
                content={"text": "不相關", "font_size_pt": 10.0},
            ),
        ),
    )


def _controller(tmp_path: Path) -> CoverController:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    controller.replace_project(dumps_project(_project(tmp_path)), clear_history=True)
    return controller


def test_group_members_returns_all_members_in_project_order(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    assert tuple(
        element.id for element in controller.group_members("back-publisher-details")
    ) == ("back-publisher-heading", "back-publisher-details")
    assert tuple(element.id for element in controller.group_members("unrelated")) == (
        "unrelated",
    )


def test_moving_heading_moves_details_by_same_delta_and_is_one_undo_step(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)

    controller.update_element(
        "back-publisher-heading",
        {"transform": {"x_mm": 13.0, "y_mm": 12.0}},
    )

    changed = loads_project(controller.project_json)
    assert changed.elements_by_id["back-publisher-heading"].transform.x_mm == 13.0
    assert changed.elements_by_id["back-publisher-heading"].transform.y_mm == 12.0
    assert changed.elements_by_id["back-publisher-details"].transform.x_mm == 13.0
    assert changed.elements_by_id["back-publisher-details"].transform.y_mm == 17.0
    assert changed.elements_by_id["unrelated"].transform.x_mm == 60.0

    controller.undo()
    restored = loads_project(controller.project_json)
    assert restored.elements_by_id["back-publisher-heading"].transform.x_mm == 10.0
    assert restored.elements_by_id["back-publisher-details"].transform.y_mm == 15.0
    assert controller.can_undo is False


def test_scaling_heading_scales_group_geometry_and_typography(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    controller.update_element(
        "back-publisher-heading",
        {
            "transform": {
                "x_mm": 10.0,
                "y_mm": 10.0,
                "width_mm": 40.0,
                "height_mm": 8.0,
            }
        },
    )

    changed = loads_project(controller.project_json)
    heading = changed.elements_by_id["back-publisher-heading"]
    details = changed.elements_by_id["back-publisher-details"]
    assert heading.transform.width_mm == pytest.approx(40.0)
    assert heading.content["font_size_pt"] == pytest.approx(15.0)
    assert details.transform == ElementTransform(10.0, 20.0, 40.0, 16.0)
    assert details.content["font_size_pt"] == pytest.approx(13.0)
    assert details.content["line_spacing_mm"] == pytest.approx(6.0)


def test_visibility_and_delete_apply_to_whole_group(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    controller.update_element("back-publisher-details", {"opacity": 0.0})
    hidden = loads_project(controller.project_json)
    assert hidden.elements_by_id["back-publisher-heading"].opacity == 0.0
    assert hidden.elements_by_id["back-publisher-details"].opacity == 0.0
    assert hidden.elements_by_id["unrelated"].opacity == 1.0

    controller.remove_element("back-publisher-heading")
    deleted = loads_project(controller.project_json)
    assert "back-publisher-heading" not in deleted.elements_by_id
    assert "back-publisher-details" not in deleted.elements_by_id
    assert "unrelated" in deleted.elements_by_id


def test_canvas_selects_entire_publisher_group(qtbot, tmp_path: Path) -> None:
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    canvas.set_project(dumps_project(_project(tmp_path)))

    canvas.select_element("back-publisher-details")

    selected_ids = {
        item.element_id
        for item in canvas.scene().selectedItems()
        if hasattr(item, "element_id")
    }
    assert selected_ids == {
        "back-publisher-heading",
        "back-publisher-details",
    }
