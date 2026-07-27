from __future__ import annotations

from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.templates import apply_template


def test_legacy_publisher_template_alias_builds_back_matter_and_spine() -> None:
    project = CoverProject(
        schema_version=1,
        source_file="book.epub",
        source_type="epub",
        metadata=CoverMetadata(
            title="範例書名",
            publisher="範例出版社",
            isbn="9780306406157",
        ),
        trim_size=TrimSize(128.0, 182.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
    )

    applied = apply_template(project, "publisher_back_matter")

    assert applied.background["active_template"] == "publisher_back_matter_with_spine"
    assert "back-isbn-code" in applied.elements_by_id
    assert "back-publisher-heading" in applied.elements_by_id
    assert "spine-background" in applied.elements_by_id
    assert "spine-title-main" in applied.elements_by_id
