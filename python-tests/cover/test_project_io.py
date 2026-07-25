from __future__ import annotations

import json
from dataclasses import replace
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
from epub_a4_word.cover.project_io import CoverValidationError, dumps_project, loads_project


def sample_project(tmp_path: Path) -> CoverProject:
    image = tmp_path / "cover.png"
    image.write_bytes(b"image-placeholder")
    return CoverProject(
        schema_version=1,
        source_file=str(tmp_path / "book.epub"),
        source_type="epub",
        metadata=CoverMetadata(title="範例書", author="作者"),
        trim_size=TrimSize(width_mm=105.0, height_mm=148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        elements=(
            CoverElement(
                id="front-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(0.0, 0.0, 105.0, 148.0),
                content={"path": str(image), "fit": "cover"},
            ),
        ),
    )


def test_project_round_trip_preserves_types(tmp_path: Path) -> None:
    restored = loads_project(dumps_project(sample_project(tmp_path)))
    assert restored.schema_version == 1
    assert restored.metadata.title == "範例書"
    assert restored.image_mode is ImageMode.FRONT_ONLY
    assert restored.elements[0].kind is ElementKind.IMAGE
    assert restored.elements[0].transform.width_mm == 105.0


def test_dump_is_deterministic_compact_utf8_json(tmp_path: Path) -> None:
    text = dumps_project(sample_project(tmp_path))
    assert text == dumps_project(sample_project(tmp_path))
    assert "範例書" in text
    assert " " not in text


def test_rejects_unknown_schema_version(tmp_path: Path) -> None:
    text = dumps_project(sample_project(tmp_path)).replace(
        '"schema_version":1', '"schema_version":2'
    )
    with pytest.raises(CoverValidationError, match="schema_version"):
        loads_project(text)


def test_rejects_duplicate_element_ids(tmp_path: Path) -> None:
    raw = json.loads(dumps_project(sample_project(tmp_path)))
    raw["elements"] *= 2
    with pytest.raises(CoverValidationError, match="重複"):
        loads_project(json.dumps(raw, ensure_ascii=False))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("page_count", 0, "page_count"),
        ("paper_caliper_mm", 0.0, "paper_caliper_mm"),
        ("manual_spine_width_mm", 0.0, "manual_spine_width_mm"),
        ("bleed_mm", -0.1, "bleed_mm"),
        ("bleed_mm", 10.1, "bleed_mm"),
        ("overlap_mm", 4.9, "overlap_mm"),
    ],
)
def test_rejects_invalid_physical_project_values(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    project = replace(sample_project(tmp_path), **{field: value})
    with pytest.raises(CoverValidationError, match=message):
        dumps_project(project)


@pytest.mark.parametrize("width_mm,height_mm", [(0.0, 148.0), (105.0, -1.0)])
def test_rejects_invalid_trim_dimensions(tmp_path: Path, width_mm: float, height_mm: float) -> None:
    project = replace(sample_project(tmp_path), trim_size=TrimSize(width_mm, height_mm))
    with pytest.raises(CoverValidationError, match="trim_size"):
        dumps_project(project)


@pytest.mark.parametrize("opacity", [-0.01, 1.01])
def test_rejects_invalid_opacity(tmp_path: Path, opacity: float) -> None:
    project = sample_project(tmp_path)
    element = replace(project.elements[0], opacity=opacity)
    with pytest.raises(CoverValidationError, match="opacity"):
        dumps_project(replace(project, elements=(element,)))


@pytest.mark.parametrize("width_mm,height_mm", [(0.0, 148.0), (105.0, 0.0)])
def test_rejects_invalid_element_dimensions(
    tmp_path: Path, width_mm: float, height_mm: float
) -> None:
    project = sample_project(tmp_path)
    transform = replace(project.elements[0].transform, width_mm=width_mm, height_mm=height_mm)
    element = replace(project.elements[0], transform=transform)
    with pytest.raises(CoverValidationError, match="寬高"):
        dumps_project(replace(project, elements=(element,)))


def test_rejects_missing_image_path(tmp_path: Path) -> None:
    project = sample_project(tmp_path)
    element = replace(project.elements[0], content={"path": str(tmp_path / "missing.png")})
    with pytest.raises(CoverValidationError, match="圖片"):
        dumps_project(replace(project, elements=(element,)))


def test_rejects_invalid_json() -> None:
    with pytest.raises(CoverValidationError, match="JSON"):
        loads_project("{")
