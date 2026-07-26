from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from PIL import Image

from epub_a4_word.cover.export_plan import build_export_plan
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
)


def test_export_plan_reports_blank_back(
    sample_project: Callable[..., CoverProject],
) -> None:
    plan = build_export_plan(sample_project(trim=(148.0, 210.0)))

    assert plan.back_cover_blank is True
    assert plan.print_plan.mode == "two_page"
    assert plan.overlap_mm == 10.0


def test_visible_back_image_makes_back_nonblank(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(148.0, 210.0))
    layout = calculate_layout(project)
    image_path = tmp_path / "back.png"
    Image.new("RGB", (400, 600), "blue").save(image_path)
    back = CoverElement(
        id="back",
        kind=ElementKind.IMAGE,
        region=Region.BACK,
        transform=ElementTransform(
            layout.back_rect.x_mm,
            layout.back_rect.y_mm,
            layout.back_rect.width_mm,
            layout.back_rect.height_mm,
        ),
        opacity=1.0,
        content={"path": str(image_path), "fit": "cover"},
    )

    plan = build_export_plan(
        replace(
            project,
            image_mode=ImageMode.SEPARATE_COVERS,
            elements=(back,),
        )
    )

    assert plan.back_cover_blank is False
