from __future__ import annotations

from dataclasses import replace

import pytest
from PIL import Image

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import LogoAssetMetadata
from epub_a4_word.cover.templates import apply_template


def _modern_project(sample_project, width: float, style: str, tmp_path):
    logo_path = tmp_path / f"logo-{width}-{style}.png"
    Image.new("RGB", (120, 80), "#DF6B32").save(logo_path)
    base = sample_project(manual_spine_width_mm=width)
    return replace(
        base,
        metadata=replace(
            base.metadata,
            title="歡迎來到實力至上主義的教室",
            english_title="Welcome to the Classroom of the Second-year",
            arc_label="二年級篇",
            volume_number="3",
            author="衣笠彰梧",
            internal_book_code="CL0308-17",
            publisher="台灣角川",
            spine_style=style,
            publisher_logo=LogoAssetMetadata(
                asset_id="test-logo",
                path=str(logo_path),
            ),
        ),
    )


def test_arc_and_volume_use_distinct_fields(sample_project, tmp_path) -> None:
    project = _modern_project(
        sample_project,
        8.0,
        "reference_stacked",
        tmp_path,
    )

    result = apply_template(project, "modern_vertical_back_with_spine")

    assert result.elements_by_id["modern-spine-arc"].content["text"] == "二年級篇"
    assert result.elements_by_id["modern-spine-volume"].content["text"] == "3"
    assert result.elements_by_id["modern-spine-english-title"].content[
        "text"
    ] == "Welcome to the Classroom of the Second-year"


@pytest.mark.parametrize("width", [4.0, 6.03, 8.0, 12.0])
@pytest.mark.parametrize(
    "style",
    ["reference_stacked", "clean_centered", "parallel_columns"],
)
def test_all_generated_spine_elements_are_clipped_to_spine(
    width, style, sample_project, tmp_path
) -> None:
    project = _modern_project(sample_project, width, style, tmp_path)
    result = apply_template(project, "modern_vertical_back_with_spine")
    spine = calculate_layout(result).spine_rect
    elements = [
        element
        for element in result.elements
        if element.id.startswith("modern-spine-")
    ]

    assert elements
    assert all(
        spine.x_mm <= element.transform.x_mm
        and element.transform.x_mm + element.transform.width_mm <= spine.right_mm
        and spine.y_mm <= element.transform.y_mm
        and element.transform.y_mm + element.transform.height_mm <= spine.bottom_mm
        for element in elements
    )
    logo = result.elements_by_id["modern-spine-logo"]
    assert logo.transform.width_mm >= spine.width_mm * 0.70
