from __future__ import annotations

import json
from pathlib import Path

import pytest
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
from epub_a4_word_desktop.cover.project_files import (
    open_project_bundle,
    save_project_bundle,
)


def _project_json(tmp_path: Path) -> tuple[str, Path]:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    image = tmp_path / "cover.png"
    Image.new("RGB", (60, 90), "white").save(image)
    project = CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="範例書", author="作者"),
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
                content={"path": str(image), "fit": "cover"},
            ),
        ),
    )
    return dumps_project(project), image


def test_saved_project_uses_relative_asset_paths(tmp_path: Path) -> None:
    project_json, _image = _project_json(tmp_path)
    destination = tmp_path / "saved" / "book.cover.json"
    path = save_project_bundle(project_json, destination)
    raw = json.loads(path.read_text("utf-8"))
    image_path = next(
        element["content"]["path"]
        for element in raw["elements"]
        if element["kind"] == "image"
    )
    assert not Path(image_path).is_absolute()
    assert (path.parent / image_path).is_file()
    assert path == destination.resolve()


def test_open_project_resolves_asset_paths_and_validates(tmp_path: Path) -> None:
    project_json, _image = _project_json(tmp_path)
    saved = save_project_bundle(project_json, tmp_path / "book.cover.json")
    opened_json = open_project_bundle(saved)
    project = loads_project(opened_json)
    image_path = Path(project.elements_by_id["front-image"].content["path"])
    assert image_path.is_absolute()
    assert image_path.is_file()
    assert project.metadata.title == "範例書"


def test_duplicate_images_are_copied_once(tmp_path: Path) -> None:
    project_json, image = _project_json(tmp_path)
    project = loads_project(project_json)
    duplicate = CoverElement(
        id="back-image",
        kind=ElementKind.IMAGE,
        region=Region.BACK,
        transform=ElementTransform(3.0, 3.0, 105.0, 148.0),
        z_index=1,
        content={"path": str(image), "fit": "cover"},
    )
    project_json = dumps_project(
        CoverProject(**{**project.__dict__, "elements": project.elements + (duplicate,)})
    )
    saved = save_project_bundle(project_json, tmp_path / "book.cover.json")
    assets = saved.parent / "book.cover_assets"
    assert len(tuple(assets.iterdir())) == 1


def test_missing_asset_aborts_with_exact_path(tmp_path: Path) -> None:
    project_json, image = _project_json(tmp_path)
    image.unlink()
    with pytest.raises(ValueError, match=str(image).replace("\\", "\\\\")):
        save_project_bundle(project_json, tmp_path / "book.cover.json")
