from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image

import android_bridge
from epub_a4_word.cover.models import (
    CoverElement,
    ElementKind,
    ElementTransform,
    Region,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word.cover.templates import apply_template


def test_cover_bridge_refreshes_template_metadata_without_resetting_geometry(
    sample_project,
) -> None:
    base = sample_project(manual_spine_width_mm=12.0)
    project = apply_template(
        replace(base, metadata=replace(base.metadata, back_vertical_copy="原始文案")),
        "modern_vertical_back_with_spine",
    )
    body = project.elements_by_id["modern-back-copy-column-1"]
    moved = replace(
        body,
        transform=replace(body.transform, x_mm=body.transform.x_mm + 1.0),
    )
    project = replace(
        project,
        elements=tuple(
            moved if item.id == moved.id else item for item in project.elements
        ),
    )
    candidate = replace(
        project,
        metadata=replace(project.metadata, back_vertical_copy="更新後的直排文案"),
    )

    refreshed = loads_project(
        android_bridge.cover_refresh_template_metadata_json(
            dumps_project(project),
            dumps_project(candidate),
        )
    )

    assert refreshed.elements_by_id[moved.id].transform == moved.transform
    assert refreshed.elements_by_id[moved.id].content["text"]


def test_cover_bridge_reflows_spine_when_style_changes(sample_project) -> None:
    base = sample_project(manual_spine_width_mm=12.0)
    metadata = replace(
        base.metadata,
        title="歡迎來到實力至上主義的教室",
        english_title="Welcome to the Classroom of the Elite",
        arc_label="二年級篇",
        volume_number="3",
        spine_style="reference_stacked",
    )
    project = apply_template(
        replace(base, metadata=metadata),
        "modern_vertical_back_with_spine",
    )
    before = project.elements_by_id["modern-spine-title"].transform
    candidate = replace(
        project,
        metadata=replace(project.metadata, spine_style="parallel_columns"),
    )

    refreshed = loads_project(
        android_bridge.cover_refresh_template_metadata_json(
            dumps_project(project),
            dumps_project(candidate),
        )
    )

    assert refreshed.metadata.spine_style == "parallel_columns"
    assert refreshed.elements_by_id["modern-spine-title"].transform != before


def test_cover_bridge_reextracts_accent_without_recreating_project(
    sample_project, tmp_path: Path
) -> None:
    cover = tmp_path / "front.png"
    Image.new("RGB", (200, 300), "#2674D9").save(cover)
    project = apply_template(
        sample_project(manual_spine_width_mm=12.0),
        "modern_vertical_back_with_spine",
    )
    custom = CoverElement(
        id="user-custom-element",
        kind=ElementKind.TEXT,
        region=Region.BACK,
        transform=ElementTransform(10.0, 100.0, 20.0, 10.0),
        content={"text": "保留我"},
    )
    source = CoverElement(
        id="source-cover-image",
        kind=ElementKind.IMAGE,
        region=Region.FRONT,
        transform=ElementTransform(120.0, 3.0, 105.0, 148.0),
        content={"path": str(cover), "fit": "cover"},
    )
    project = replace(project, elements=(*project.elements, custom, source))

    refreshed = loads_project(
        android_bridge.cover_reextract_accent_json(dumps_project(project))
    )

    assert "user-custom-element" in refreshed.elements_by_id
    assert refreshed.metadata.accent_color_mode == "auto"
    assert refreshed.metadata.extracted_accent_color
