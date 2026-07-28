from __future__ import annotations

from dataclasses import dataclass

from .geometry import CoverLayout
from .models import CoverProject


@dataclass(frozen=True)
class CropFrameLine:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    width_pt: float = 0.35


def build_crop_frame(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CropFrameLine, ...]:
    if not project.export_settings.show_crop_marks:
        return ()
    rect = layout.spread_rect
    lines = (
        CropFrameLine(rect.x_mm, rect.y_mm, rect.right_mm, rect.y_mm),
        CropFrameLine(rect.right_mm, rect.y_mm, rect.right_mm, rect.bottom_mm),
        CropFrameLine(rect.right_mm, rect.bottom_mm, rect.x_mm, rect.bottom_mm),
        CropFrameLine(rect.x_mm, rect.bottom_mm, rect.x_mm, rect.y_mm),
    )
    bleed = layout.bleed_rect
    for line in lines:
        if not (
            bleed.x_mm <= line.x1_mm <= bleed.right_mm
            and bleed.x_mm <= line.x2_mm <= bleed.right_mm
            and bleed.y_mm <= line.y1_mm <= bleed.bottom_mm
            and bleed.y_mm <= line.y2_mm <= bleed.bottom_mm
        ):
            raise ValueError("裁切框超出出血範圍。")
    return lines
