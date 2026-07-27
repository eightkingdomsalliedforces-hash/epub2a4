from __future__ import annotations

from dataclasses import replace
from typing import Callable

import pytest

from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
)
from epub_a4_word.cover.templates import STANDARD_TEMPLATE_IDS, apply_template, list_templates


@pytest.mark.parametrize(
    "template_id",
    [
        "minimal_text",
        "front_image_plain_back",
        "full_spread",
        "top_bottom_blocks",
    ],
)
def test_template_creates_unique_standard_elements(
    sample_project: Callable[..., CoverProject], template_id: str
) -> None:
    result = apply_template(sample_project(), template_id)
    assert len({element.id for element in result.elements}) == len(result.elements)
    if template_id in {"minimal_text", "top_bottom_blocks"}:
        assert any(element.id == "front-title" for element in result.elements)
        assert any(element.id == "front-author" for element in result.elements)
        assert any(element.id == "spine-title" for element in result.elements)
        assert any(element.id == "back-description" for element in result.elements)
        assert any(element.id == "back-publisher" for element in result.elements)
        assert any(element.id == "back-isbn" for element in result.elements)
    elif template_id == "front_image_plain_back":
        assert not any(element.id == "front-title" for element in result.elements)
        assert not any(element.id == "front-author" for element in result.elements)
        assert any(element.id == "spine-title" for element in result.elements)
        assert any(element.id == "back-description" for element in result.elements)
    else:
        assert not any(element.id in STANDARD_TEMPLATE_IDS for element in result.elements)


def test_full_spread_template_sets_image_mode(
    sample_project: Callable[..., CoverProject],
) -> None:
    result = apply_template(sample_project(), "full_spread")
    assert result.image_mode is ImageMode.FULL_SPREAD


def test_template_catalog_is_deterministic() -> None:
    first = list_templates()
    second = list_templates()
    assert first == second
    assert [item.id for item in first] == [
        "minimal_text",
        "front_image_plain_back",
        "full_spread",
        "top_bottom_blocks",
        "publisher_back_matter_with_spine",
    ]


def test_apply_template_preserves_user_elements(
    sample_project: Callable[..., CoverProject],
) -> None:
    custom = CoverElement(
        id="user-note",
        kind=ElementKind.TEXT,
        region=Region.FRONT,
        transform=ElementTransform(20.0, 20.0, 30.0, 10.0),
        content={"text": "保留我"},
    )
    project = replace(sample_project(), elements=(custom,))
    result = apply_template(project, "minimal_text")
    assert result.elements_by_id["user-note"] == custom


def test_reapplying_template_replaces_standard_elements_without_duplicates(
    sample_project: Callable[..., CoverProject],
) -> None:
    first = apply_template(sample_project(), "minimal_text")
    second = apply_template(first, "top_bottom_blocks")
    assert len({element.id for element in second.elements}) == len(second.elements)
    assert len([element for element in second.elements if element.id == "front-title"]) == 1


def test_spine_under_two_mm_omits_text_and_adds_warning_without_mutating_input(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project(manual_spine_width_mm=1.5)
    result = apply_template(project, "minimal_text")
    assert not any(element.region is Region.SPINE for element in result.elements)
    assert any("小於 2 mm" in warning for warning in result.background["warnings"])
    assert "warnings" not in project.background


def test_spine_under_four_mm_uses_six_point_title_and_omits_author(
    sample_project: Callable[..., CoverProject],
) -> None:
    result = apply_template(
        sample_project(manual_spine_width_mm=3.0), "minimal_text"
    )
    assert result.elements_by_id["spine-title"].content["font_size_pt"] == 6.0
    assert "spine-author" not in result.elements_by_id


def test_unknown_template_is_rejected(sample_project: Callable[..., CoverProject]) -> None:
    with pytest.raises(ValueError, match="未知封面模板"):
        apply_template(sample_project(), "unknown")
