from __future__ import annotations

from dataclasses import replace

import pytest

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


def test_adding_translator_expands_details_without_moving_user_geometry(
    sample_project,
) -> None:
    project = apply_template(
        replace(
            sample_project(manual_spine_width_mm=12.0),
            metadata=replace(
                sample_project().metadata,
                publisher="台灣角川",
                price="NT$110/HK$35",
                publication_place="香港代理：角川洲立出版",
                translator="",
            ),
        ),
        "publisher_back_matter_with_spine",
    )
    old = project.elements_by_id["back-publisher-details"]
    moved = ElementTransform(
        old.transform.x_mm + 2.0,
        old.transform.y_mm + 3.0,
        old.transform.width_mm - 1.0,
        old.transform.height_mm,
        old.transform.rotation_deg,
    )
    project = replace(
        project,
        elements=tuple(
            replace(element, transform=moved)
            if element.id == "back-publisher-details"
            else element
            for element in project.elements
        ),
    )

    refreshed = refresh_template_metadata(
        project,
        replace(project.metadata, translator="李彥樺"),
    )
    details = refreshed.elements_by_id["back-publisher-details"]

    assert "譯者：李彥樺" in details.content["text"]
    assert details.transform.x_mm == moved.x_mm
    assert details.transform.y_mm == moved.y_mm
    assert details.transform.width_mm == moved.width_mm
    assert details.transform.height_mm > moved.height_mm


def test_wrapped_heading_pushes_details_down_without_losing_user_x_or_width(
    sample_project,
) -> None:
    project = apply_template(
        replace(
            sample_project(manual_spine_width_mm=12.0),
            metadata=replace(
                sample_project().metadata,
                publisher="角川",
                price="NT$110",
            ),
        ),
        "publisher_back_matter_with_spine",
    )
    old_heading = project.elements_by_id["back-publisher-heading"].transform
    old_details = project.elements_by_id["back-publisher-details"].transform

    refreshed = refresh_template_metadata(
        project,
        replace(
            project.metadata,
            publisher="非常非常非常非常非常非常非常非常非常非常長的出版社名稱",
        ),
    )
    heading = refreshed.elements_by_id["back-publisher-heading"].transform
    details = refreshed.elements_by_id["back-publisher-details"].transform

    growth = heading.height_mm - old_heading.height_mm
    assert growth > 0
    assert heading.x_mm == old_heading.x_mm
    assert heading.width_mm == old_heading.width_mm
    assert details.x_mm == old_details.x_mm
    assert details.width_mm == old_details.width_mm
    assert details.y_mm == pytest.approx(old_details.y_mm + growth)
