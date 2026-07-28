from __future__ import annotations

from dataclasses import replace

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.templates import apply_template, list_templates


def test_modern_template_matches_reference_regions(sample_project) -> None:
    base = sample_project(manual_spine_width_mm=12.0)
    metadata = replace(
        base.metadata,
        isbn="9786263211094",
        publisher="台灣角川",
        price="NT$240/HK$80",
        translator="Arieru",
        back_vertical_copy="以四季如夏的無人島為舞台，全年級互相競爭。",
        back_highlight_copy="綾小路同學，你最好趁現在跟人多一點的小組。",
        spine_accent_color="#DF6B32",
    )

    result = apply_template(
        replace(base, metadata=metadata),
        "modern_vertical_back_with_spine",
    )

    ids = result.elements_by_id
    safe = calculate_layout(result).back_safe_rect
    assert result.background["active_template"] == "modern_vertical_back_with_spine"
    assert ids["back-isbn-code"].transform.y_mm < ids[
        "modern-back-copy-column-1"
    ].transform.y_mm
    assert ids["modern-back-highlight-column-1"].content["color"] == "#DF6B32"
    assert not any(
        element.id.startswith("modern-back-bottom-decoration")
        for element in result.elements
    )
    assert all(
        element.transform.y_mm + element.transform.height_mm
        <= safe.y_mm + safe.height_mm * 0.90 + 1e-9
        for element in result.elements
        if element.id.startswith("modern-back-")
    )


def test_modern_template_is_listed_and_reapplication_has_unique_ids(
    sample_project,
) -> None:
    ids = {summary.id for summary in list_templates()}
    assert "modern_vertical_back_with_spine" in ids

    once = apply_template(
        sample_project(manual_spine_width_mm=12.0),
        "modern_vertical_back_with_spine",
    )
    twice = apply_template(once, "modern_vertical_back_with_spine")
    element_ids = [element.id for element in twice.elements]

    assert len(element_ids) == len(set(element_ids))
