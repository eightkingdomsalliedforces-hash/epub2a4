from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image

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
from epub_a4_word_desktop.cover.models import patch_element


class CapturingPool:
    def __init__(self) -> None:
        self.worker = None

    def start(self, worker) -> None:
        self.worker = worker


def make_project(tmp_path: Path) -> CoverProject:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(
            title="範例書名",
            author="範例作者",
            description="封底說明",
        ),
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
                transform=ElementTransform(120.0, 20.0, 90.0, 24.0),
                z_index=10,
                content={"text": "範例書名", "font_size_pt": 24.0},
            ),
        ),
    )


def make_png(path: Path) -> Path:
    Image.new("RGB", (32, 48), "white").save(path, format="PNG")
    return path


def test_patch_element_merges_nested_transform_and_content(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    changed = patch_element(
        project,
        "front-title",
        {"transform": {"x_mm": 10.0}, "content": {"text": "新書名"}},
    )
    element = changed.elements_by_id["front-title"]
    assert element.transform.x_mm == 10.0
    assert element.transform.y_mm == 20.0
    assert element.content["text"] == "新書名"
    assert element.content["font_size_pt"] == 24.0


def test_update_element_is_undoable_and_redoable(qtbot, tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    project_json = dumps_project(make_project(tmp_path))
    controller.replace_project(project_json, clear_history=True)
    before = loads_project(controller.project_json)

    with qtbot.waitSignal(controller.project_changed):
        controller.update_element("front-title", {"transform": {"x_mm": 10.0}})

    assert (
        loads_project(controller.project_json)
        .elements_by_id["front-title"]
        .transform.x_mm
        == 10.0
    )
    controller.undo()
    assert loads_project(controller.project_json) == before
    controller.redo()
    assert (
        loads_project(controller.project_json)
        .elements_by_id["front-title"]
        .transform.x_mm
        == 10.0
    )


def test_local_image_is_copied_to_working_assets(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    controller.replace_project(dumps_project(make_project(tmp_path)), clear_history=True)
    source_png = make_png(tmp_path / "source.png")

    element_id = controller.add_local_image(source_png, Region.FRONT)

    project = loads_project(controller.project_json)
    element = project.elements_by_id[element_id]
    copied = Path(element.content["path"])
    assert copied.parent == (tmp_path / "assets").resolve()
    assert copied.is_file()
    assert copied != source_png
    assert element.kind is ElementKind.IMAGE
    assert element.region is Region.FRONT


def test_remove_element_can_be_undone(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    controller.replace_project(dumps_project(make_project(tmp_path)), clear_history=True)
    controller.remove_element("front-title")
    assert "front-title" not in loads_project(controller.project_json).elements_by_id
    controller.undo()
    assert "front-title" in loads_project(controller.project_json).elements_by_id


def test_template_application_is_undoable(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    original = dumps_project(make_project(tmp_path))
    controller.replace_project(original, clear_history=True)
    controller.apply_template("top_bottom_blocks")
    changed = loads_project(controller.project_json)
    assert "template-front-top-block" in changed.elements_by_id
    controller.undo()
    assert loads_project(controller.project_json) == loads_project(original)


def test_replace_project_with_clear_history_disables_undo(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    original = dumps_project(make_project(tmp_path))
    controller.replace_project(original, clear_history=True)
    controller.update_element("front-title", {"opacity": 0.5})
    assert controller.can_undo is True
    controller.replace_project(original, clear_history=True)
    assert controller.can_undo is False


def test_editor_preview_excludes_interactive_items_to_avoid_ghosting(tmp_path: Path) -> None:
    image_path = make_png(tmp_path / "interactive.png")
    project = make_project(tmp_path)
    project = replace(
        project,
        elements=project.elements
        + (
            CoverElement(
                id="front-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(116.0, 3.0, 105.0, 148.0),
                z_index=0,
                content={"path": str(image_path), "fit": "cover"},
            ),
            CoverElement(
                id="back-barcode",
                kind=ElementKind.BARCODE_PLACEHOLDER,
                region=Region.BACK,
                transform=ElementTransform(8.0, 8.0, 38.0, 18.0),
                z_index=10,
                content={"isbn": "9780306406157"},
            ),
            CoverElement(
                id="background-shape",
                kind=ElementKind.SHAPE,
                region=Region.BACK,
                transform=ElementTransform(3.0, 3.0, 105.0, 148.0),
                z_index=-10,
                content={"shape": "rectangle", "fill": "#ffffff", "stroke": None},
            ),
        ),
    )
    pool = CapturingPool()
    controller = CoverController(
        service=object(),
        pool=pool,
        working_dir=tmp_path,
        auto_preview=False,
    )
    controller.replace_project(dumps_project(project), clear_history=True)

    controller._start_preview()

    assert pool.worker is not None
    preview_project = loads_project(pool.worker.project_json)
    assert tuple(element.id for element in preview_project.elements) == ("background-shape",)
