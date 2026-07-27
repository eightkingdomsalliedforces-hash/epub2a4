from __future__ import annotations

from dataclasses import replace

import pytest

from epub_a4_word.cover.models import CoverMetadata
from epub_a4_word.cover.templates import apply_template


@pytest.mark.parametrize(
    ("width_mm", "expected_ids", "absent_ids"),
    [
        (
            12.0,
            {
                "spine-background",
                "spine-title-main",
                "spine-title-english",
                "spine-volume",
                "spine-arc",
                "spine-author",
                "spine-internal-code",
                "spine-publisher-name",
            },
            set(),
        ),
        (
            8.0,
            {
                "spine-background",
                "spine-title-main",
                "spine-title-english",
                "spine-volume",
                "spine-author",
                "spine-publisher-name",
            },
            {"spine-arc", "spine-internal-code"},
        ),
        (
            4.0,
            {
                "spine-background",
                "spine-title-main",
                "spine-volume",
                "spine-publisher-name",
            },
            {
                "spine-title-english",
                "spine-arc",
                "spine-author",
                "spine-internal-code",
            },
        ),
    ],
)
def test_combined_publisher_template_uses_spine_width_breakpoints(
    sample_project,
    width_mm: float,
    expected_ids: set[str],
    absent_ids: set[str],
) -> None:
    metadata = CoverMetadata(
        title="魔法禁書目錄",
        author="鎌池和馬",
        publisher="台灣角川",
        english_title="A Certain Magical Index",
        volume_number="1",
        arc_label="舊約",
        internal_book_code="CL0308-17",
        spine_accent_color="#F15A24",
    )
    project = replace(
        sample_project(manual_spine_width_mm=width_mm),
        metadata=metadata,
    )

    result = apply_template(project, "publisher_back_matter_with_spine")
    ids = set(result.elements_by_id)

    assert result.background["active_template"] == "publisher_back_matter_with_spine"
    assert expected_ids <= ids
    assert ids.isdisjoint(absent_ids)
    assert result.elements_by_id["spine-background"].content["fill"] == "#ffffff"
    assert all(
        result.elements_by_id[element_id].content.get("group_id") == "publisher-spine-stack"
        for element_id in expected_ids - {"spine-background"}
    )


def test_old_publisher_template_id_is_canonicalized_to_combined_template(sample_project) -> None:
    result = apply_template(sample_project(manual_spine_width_mm=8.0), "publisher_back_matter")

    assert result.background["active_template"] == "publisher_back_matter_with_spine"
    assert "spine-title-main" in result.elements_by_id
    assert "back-publisher-heading" in result.elements_by_id


def test_wide_publisher_spine_matches_reference_vertical_typography(sample_project) -> None:
    project = replace(
        sample_project(manual_spine_width_mm=12.0),
        metadata=CoverMetadata(
            title="歡迎來到實力至上主義的教室",
            author="衣笠彰梧",
            publisher="台灣角川",
            english_title="Welcome to the Classroom",
            volume_number="2",
        ),
    )

    result = apply_template(project, "publisher_back_matter_with_spine")

    title = result.elements_by_id["spine-title-main"]
    author = result.elements_by_id["spine-author"]
    publisher = result.elements_by_id["spine-publisher-name"]
    assert title.content["direction"] == "vertical"
    assert title.transform.rotation_deg == 0.0
    assert title.content["font_size_pt"] >= 14.0
    assert author.content["direction"] == "vertical"
    assert author.content["font_size_pt"] >= 10.0
    assert publisher.content["direction"] == "vertical"
    assert publisher.content["font_size_pt"] >= 10.0
