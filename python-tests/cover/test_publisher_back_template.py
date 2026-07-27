from __future__ import annotations

from dataclasses import replace
from typing import Callable

import pytest

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import CoverMetadata, CoverProject, ElementKind, Region
from epub_a4_word.cover.templates import apply_template, list_templates


def _relative_transform(transform, safe) -> tuple[float, float, float, float]:
    return (
        (transform.x_mm - safe.x_mm) / safe.width_mm,
        (transform.y_mm - safe.y_mm) / safe.height_mm,
        transform.width_mm / safe.width_mm,
        transform.height_mm / safe.height_mm,
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
            translator="李彥樺",
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
    heading = result.elements_by_id["back-publisher-heading"]
    details = result.elements_by_id["back-publisher-details"]
    assert heading.region is Region.BACK
    assert heading.content["text"] == "範例出版社"
    assert heading.content["font_role"] == "publisher_heading"
    assert details.content["text"] == "定價：NT$320\n台北\n譯者：李彥樺"
    assert details.content["font_role"] == "publisher_details"
    assert heading.content["group_id"] == "publisher-info-stack"
    assert details.content["group_id"] == "publisher-info-stack"
    assert heading.content["layout_role"] == "heading"
    assert details.content["layout_role"] == "details"
    assert heading.transform.x_mm == pytest.approx(details.transform.x_mm)
    assert details.transform.y_mm == pytest.approx(
        heading.transform.y_mm + heading.transform.height_mm + 1.0
    )
    assert "back-publisher-info" not in result.elements_by_id
    assert not any(element.kind is ElementKind.IMAGE for element in result.elements)


def test_publisher_template_matches_reference_layout(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            isbn="9780306406157",
            publisher="台灣角川",
            price="定價：NT$110",
            publication_place="臺灣出版",
        ),
    )
    result = apply_template(project, "publisher_back_matter")
    safe = calculate_layout(result).back_safe_rect

    label = result.elements_by_id["back-isbn-label"]
    barcode = result.elements_by_id["back-isbn-code"]
    heading = result.elements_by_id["back-publisher-heading"]
    details = result.elements_by_id["back-publisher-details"]
    assert _relative_transform(label.transform, safe) == pytest.approx(
        (0.03, 0.025, 0.39, 0.028), abs=0.01
    )
    assert _relative_transform(barcode.transform, safe) == pytest.approx(
        (0.03, 0.060, 0.44, 0.125), abs=0.015
    )
    heading_relative = _relative_transform(heading.transform, safe)
    details_relative = _relative_transform(details.transform, safe)
    assert heading_relative[0] == pytest.approx(0.49, abs=0.015)
    assert heading_relative[1] == pytest.approx(0.025, abs=0.015)
    assert heading_relative[2] == pytest.approx(0.38, abs=0.015)
    assert details_relative[0] == pytest.approx(0.49, abs=0.015)
    assert details_relative[2] == pytest.approx(0.38, abs=0.015)
    assert details.transform.y_mm == pytest.approx(
        heading.transform.y_mm + heading.transform.height_mm + 1.0
    )
    slot = result.background["publisher_logo_slot"]
    assert (
        (slot["x_mm"] - safe.x_mm) / safe.width_mm,
        (slot["y_mm"] - safe.y_mm) / safe.height_mm,
        slot["width_mm"] / safe.width_mm,
        slot["height_mm"] / safe.height_mm,
    ) == pytest.approx((0.26, 0.34, 0.48, 0.36), abs=0.01)
    assert label.content["text"] == "ISBN 978-030-640-615-7"
    assert label.content["font_role"] == "ocr"
    assert heading.content["font_size_pt"] == pytest.approx(7.5)
    assert details.content["font_size_pt"] == pytest.approx(6.5)
    assert heading.content["align"] == "left"
    assert details.content["align"] == "left"


def test_publisher_details_start_at_stack_top_when_heading_is_missing(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    project = replace(
        project,
        metadata=replace(project.metadata, publisher="", price="NT$110"),
    )
    result = apply_template(project, "publisher_back_matter")
    safe = calculate_layout(result).back_safe_rect

    assert "back-publisher-heading" not in result.elements_by_id
    details = result.elements_by_id["back-publisher-details"]
    assert details.transform.y_mm == pytest.approx(
        safe.y_mm + safe.height_mm * 0.025
    )


def test_publisher_template_hides_missing_fields_without_placeholders(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    project = replace(project, metadata=CoverMetadata(title=project.metadata.title))
    result = apply_template(project, "publisher_back_matter")

    assert "back-isbn-label" not in result.elements_by_id
    assert "back-isbn-code" not in result.elements_by_id
    assert "back-publisher-info" not in result.elements_by_id
    assert "back-publisher-heading" not in result.elements_by_id
    assert "back-publisher-details" not in result.elements_by_id
    assert all("ISBN" not in str(element.content.get("text", "")) for element in result.elements)


def test_publisher_template_does_not_overlay_front_text_on_source_cover(
    sample_project: Callable[..., CoverProject],
    tmp_path,
) -> None:
    from PIL import Image
    from epub_a4_word.cover.models import CoverElement, ElementTransform

    project = sample_project(trim=(128.0, 182.0), page_count=160)
    layout = calculate_layout(project)
    cover_path = tmp_path / "source-front.png"
    Image.new("RGB", (600, 900), "white").save(cover_path)
    project = replace(
        project,
        elements=(
            CoverElement(
                id="source-cover-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(
                    layout.front_rect.x_mm,
                    layout.front_rect.y_mm,
                    layout.front_rect.width_mm,
                    layout.front_rect.height_mm,
                ),
                z_index=-15,
                content={"path": str(cover_path), "fit": "cover"},
            ),
        ),
    )

    result = apply_template(project, "publisher_back_matter")

    assert "front-title" not in result.elements_by_id
    assert "front-author" not in result.elements_by_id
    assert "source-cover-image" in result.elements_by_id
