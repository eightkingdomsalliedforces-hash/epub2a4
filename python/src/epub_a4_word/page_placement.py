from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .pagination import LayoutSettings, resolve_layout

GuideRole = Literal["crop", "fold"]


@dataclass(frozen=True)
class CropGuide:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    role: GuideRole = "crop"


@dataclass(frozen=True)
class PagePlacement:
    paper_width_mm: float
    paper_height_mm: float
    content_x_mm: float
    content_y_mm: float
    content_width_mm: float
    content_height_mm: float
    guides: tuple[CropGuide, ...]


def _mm(cm: float | None, label: str) -> float:
    if cm is None:
        raise ValueError(f"未解析的版面欄位：{label}")
    return float(cm) * 10.0


def build_page_placement(settings: LayoutSettings) -> PagePlacement:
    resolved = resolve_layout(settings)
    paper_width = _mm(resolved.paper_width_cm, "paper_width_cm")
    paper_height = _mm(resolved.paper_height_cm, "paper_height_cm")
    content_x = _mm(resolved.page_margin_left_cm, "page_margin_left_cm")
    content_y = _mm(resolved.page_margin_top_cm, "page_margin_top_cm")
    rows = int(resolved.grid_rows or 1)
    cols = int(resolved.grid_cols or 1)
    cell_width = _mm(resolved.cell_width_cm, "cell_width_cm")
    cell_height = _mm(resolved.cell_height_cm, "cell_height_cm")
    if resolved.imposition_mode in {"four_up", "signature16"}:
        content_y += _mm(
            resolved.page_prefix_height_cm,
            "page_prefix_height_cm",
        )
    content_width = cell_width * cols
    content_height = cell_height * rows

    guides: list[CropGuide] = []
    if (
        resolved.imposition_mode == "b6_on_a5"
        and resolved.output_mark_mode == "crop_marks"
    ):
        guides.extend(
            (
                CropGuide(0.0, content_y, paper_width, content_y, "crop"),
                CropGuide(content_x, 0.0, content_x, paper_height, "crop"),
            )
        )
    elif (
        resolved.imposition_mode in {"four_up", "signature16"}
        and resolved.cut_guides
    ):
        role: GuideRole = (
            "fold" if resolved.imposition_mode == "signature16" else "crop"
        )
        for column in range(1, cols):
            x = content_x + cell_width * column
            guides.append(
                CropGuide(
                    x,
                    content_y,
                    x,
                    content_y + content_height,
                    role,
                )
            )
        for row in range(1, rows):
            y = content_y + cell_height * row
            guides.append(
                CropGuide(
                    content_x,
                    y,
                    content_x + content_width,
                    y,
                    role,
                )
            )

    return PagePlacement(
        paper_width_mm=paper_width,
        paper_height_mm=paper_height,
        content_x_mm=content_x,
        content_y_mm=content_y,
        content_width_mm=content_width,
        content_height_mm=content_height,
        guides=tuple(guides),
    )
