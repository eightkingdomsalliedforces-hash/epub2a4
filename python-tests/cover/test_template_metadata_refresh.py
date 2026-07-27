from __future__ import annotations

from dataclasses import replace

from epub_a4_word.cover.models import ElementTransform
from epub_a4_word.cover.templates import apply_template, refresh_template_metadata


def test_metadata_refresh_preserves_existing_template_geometry(sample_project) -> None:
    project = apply_template(
        replace(
            sample_project(manual_spine_width_mm=8.0),
            metadata=replace(
                sample_project().metadata,
                publisher="台灣角川",
                english_title="Index",
                volume_number="1",
            ),
        ),
        "publisher_back_matter_with_spine",
    )
    moved = ElementTransform(11.0, 22.0, 7.0, 90.0, 90.0)
    elements = tuple(
        replace(element, transform=moved, opacity=0.7, z_index=77)
        if element.id == "spine-title-main"
        else element
        for element in project.elements
    )
    project = replace(project, elements=elements)

    refreshed = refresh_template_metadata(
        project,
        replace(project.metadata, title="新書名", english_title="New subtitle"),
    )
    title = refreshed.elements_by_id["spine-title-main"]

    assert title.content["text"] == "新書名"
    assert title.transform == moved
    assert title.opacity == 0.7
    assert title.z_index == 77


def test_empty_field_hides_element_and_restoring_value_reuses_geometry(sample_project) -> None:
    project = apply_template(
        replace(
            sample_project(manual_spine_width_mm=12.0),
            metadata=replace(sample_project().metadata, arc_label="舊約"),
        ),
        "publisher_back_matter_with_spine",
    )
    old = project.elements_by_id["spine-arc"]

    hidden = refresh_template_metadata(
        project,
        replace(project.metadata, arc_label=""),
    )
    assert hidden.elements_by_id["spine-arc"].opacity == 0.0

    restored = refresh_template_metadata(
        hidden,
        replace(hidden.metadata, arc_label="新約"),
    )
    element = restored.elements_by_id["spine-arc"]
    assert element.content["text"] == "新約"
    assert element.transform == old.transform
    assert element.opacity == old.opacity
