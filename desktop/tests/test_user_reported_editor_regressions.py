from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QRectF

from epub_a4_word.cover.composition import CompositionSelection
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
from epub_a4_word.cover.search.models import CandidateCategory
from epub_a4_word_desktop.cover.controller import CoverController
from epub_a4_word_desktop.cover.items import CoverTextItem


def _png(path: Path, color: str) -> Path:
    Image.new("RGB", (60, 90), color).save(path)
    return path


def _project(tmp_path: Path) -> CoverProject:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    old_front = _png(tmp_path / "old-front.png", "white")
    old_back = _png(tmp_path / "old-back.png", "gray")
    return CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="魔法禁書目錄 1", author="鎌池和馬"),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.SEPARATE_COVERS,
        working_dir=str(tmp_path),
        elements=(
            CoverElement(
                id="source-cover-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(116.0, 3.0, 105.0, 148.0),
                z_index=-15,
                content={"path": str(old_front), "fit": "cover"},
            ),
            CoverElement(
                id="source-back-cover-image",
                kind=ElementKind.IMAGE,
                region=Region.BACK,
                transform=ElementTransform(3.0, 3.0, 105.0, 148.0),
                z_index=-15,
                content={"path": str(old_back), "fit": "cover"},
            ),
        ),
    )


def test_downloaded_front_replaces_existing_front_cover(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path / "work", auto_preview=False)
    controller.replace_project(dumps_project(_project(tmp_path)), clear_history=True)
    new_front = _png(tmp_path / "new-front.png", "red")

    controller.add_downloaded_images(
        {
            CandidateCategory.FRONT: CompositionSelection(
                path=new_front,
                category=CandidateCategory.FRONT,
            )
        }
    )

    updated = loads_project(controller.project_json)
    overlapping = tuple(
        element
        for element in updated.elements
        if element.kind is ElementKind.IMAGE
        and element.region in {Region.FRONT, Region.SPREAD}
    )
    assert len(overlapping) == 1
    assert Path(str(overlapping[0].content["path"])).name.endswith("new-front.png")
    assert "source-cover-image" not in updated.elements_by_id
    assert "source-back-cover-image" in updated.elements_by_id


def test_composed_spread_replaces_all_existing_cover_images(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path / "work", auto_preview=False)
    controller.replace_project(dumps_project(_project(tmp_path)), clear_history=True)
    spread = _png(tmp_path / "spread.png", "blue")

    added_id = controller.add_composed_spread(spread)

    updated = loads_project(controller.project_json)
    images = tuple(element for element in updated.elements if element.kind is ElementKind.IMAGE)
    assert tuple(element.id for element in images) == (added_id,)
    assert images[0].region is Region.SPREAD


def test_selection_controls_are_inside_item_bounding_rect(tmp_path: Path) -> None:
    element = CoverElement(
        id="text",
        kind=ElementKind.TEXT,
        region=Region.BACK,
        transform=ElementTransform(0.0, 0.0, 40.0, 20.0),
        content={"text": "台灣角川", "font_size_pt": 7.5},
    )
    item = CoverTextItem(element)

    assert item.contentRect() == QRectF(0.0, 0.0, 40.0, 20.0)
    bounds = item.boundingRect()
    half = item.HANDLE_SIZE_MM / 2.0
    assert bounds.left() <= -half
    assert bounds.right() >= 40.0 + half
    assert bounds.bottom() >= 20.0 + half
    assert bounds.top() <= -(5.0 + half)


def test_qt_canvas_converts_point_size_to_scene_millimetres() -> None:
    element = CoverElement(
        id="text",
        kind=ElementKind.TEXT,
        region=Region.BACK,
        transform=ElementTransform(0.0, 0.0, 60.0, 20.0),
        content={
            "text": "台灣角川",
            "font_size_pt": 24.0,
            "font_role": "publisher_heading",
        },
    )
    item = CoverTextItem(element)

    font = item._font()

    assert font.pixelSize() == pytest.approx(round(24.0 * 25.4 / 72.0), abs=1)
    assert font.pixelSize() < 12
