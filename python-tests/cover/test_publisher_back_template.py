from __future__ import annotations

from dataclasses import replace
from typing import Callable

from PIL import Image

from epub_a4_word.cover.models import CoverMetadata, CoverProject, ElementKind, Region
from epub_a4_word.cover.templates import (
    apply_template,
    assign_publisher_logo,
    list_templates,
)


def test_publisher_template_catalog_entry_is_available() -> None:
    summaries = {item.id: item for item in list_templates()}
    assert summaries["publisher_back_matter"].name == "出版社式封底"


def test_publisher_template_creates_only_non_empty_editable_fields(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            isbn="9780306406157",
            publisher="範例出版社",
            price="NT$320",
            publication_place="台北",
            isbn_addon="50320",
        ),
    )
    result = apply_template(project, "publisher_back_matter")

    assert result.background["color"] == "#ffffff"
    assert result.background["active_template"] == "publisher_back_matter"
    assert set(result.background["publisher_logo_slot"]) == {
        "x_mm",
        "y_mm",
        "width_mm",
        "height_mm",
    }
    assert result.elements_by_id["back-isbn-label"].kind is ElementKind.TEXT
    barcode = result.elements_by_id["back-isbn-code"]
    assert barcode.kind is ElementKind.BARCODE_PLACEHOLDER
    assert barcode.content["isbn"] == "9780306406157"
    assert barcode.content["addon"] == "50320"
    assert result.elements_by_id["back-isbn-label"].content["font_size_pt"] >= 10.0
    info = result.elements_by_id["back-publisher-info"]
    assert info.region is Region.BACK
    assert info.content["font_size_pt"] >= 10.0
    assert info.content["text"] == "範例出版社\nNT$320\n台北"
    assert not any(element.kind is ElementKind.IMAGE for element in result.elements)


def test_publisher_template_hides_missing_fields_without_placeholders(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    project = replace(project, metadata=CoverMetadata(title=project.metadata.title))
    result = apply_template(project, "publisher_back_matter")

    assert "back-isbn-label" not in result.elements_by_id
    assert "back-isbn-code" not in result.elements_by_id
    assert "back-publisher-info" not in result.elements_by_id
    assert all("ISBN" not in str(element.content.get("text", "")) for element in result.elements)


def test_assigning_publisher_logo_replaces_the_previous_logo(
    sample_project: Callable[..., CoverProject],
    tmp_path,
) -> None:
    project = apply_template(sample_project(), "publisher_back_matter")

    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    Image.new("RGB", (20, 20), "red").save(first_path)
    Image.new("RGB", (20, 20), "blue").save(second_path)

    first = assign_publisher_logo(project, first_path)
    second = assign_publisher_logo(first, second_path)

    logos = [element for element in second.elements if element.id == "back-publisher-logo"]
    assert len(logos) == 1
    assert logos[0].region is Region.BACK
    assert logos[0].content["path"] == str(second_path.resolve())
    spine_logo = second.elements_by_id["spine-publisher-logo"]
    assert spine_logo.region is Region.SPINE
    assert spine_logo.content["path"] == logos[0].content["path"]
    assert spine_logo.transform.width_mm >= 5.2
