from __future__ import annotations

from dataclasses import dataclass

from .geometry import CoverLayout, RectMm, calculate_layout
from .models import CoverElement, CoverProject, ElementKind, ImageMode, Region
from .print_plan import PrintPlan, build_print_plan


@dataclass(frozen=True)
class CoverExportPlan:
    original_size_mm: tuple[float, float]
    print_plan: PrintPlan
    back_cover_blank: bool

    @property
    def overlap_mm(self) -> float:
        if len(self.print_plan.pages) != 2:
            return 0.0
        back, front = self.print_plan.pages
        return max(0.0, back.right_overlap_mm + front.left_overlap_mm)


def _intersection(first: RectMm, second: RectMm) -> RectMm | None:
    left = max(first.x_mm, second.x_mm)
    top = max(first.y_mm, second.y_mm)
    right = min(first.right_mm, second.right_mm)
    bottom = min(first.bottom_mm, second.bottom_mm)
    if right <= left or bottom <= top:
        return None
    return RectMm(left, top, right - left, bottom - top)


def _element_rect(element: CoverElement) -> RectMm:
    transform = element.transform
    return RectMm(
        float(transform.x_mm),
        float(transform.y_mm),
        float(transform.width_mm),
        float(transform.height_mm),
    )


def _image_clip(project: CoverProject, layout: CoverLayout, element: CoverElement) -> RectMm | None:
    rect = _element_rect(element)
    if project.image_mode is ImageMode.FRONT_ONLY:
        return _intersection(rect, layout.front_rect)
    if project.image_mode is ImageMode.SEPARATE_COVERS:
        region_rect = {
            Region.BACK: layout.back_rect,
            Region.SPINE: layout.spine_rect,
            Region.FRONT: layout.front_rect,
            Region.SPREAD: layout.bleed_rect,
        }[element.region]
        return _intersection(rect, region_rect)
    return _intersection(rect, layout.bleed_rect)


def _has_visible_back_image(project: CoverProject, layout: CoverLayout) -> bool:
    for element in project.elements:
        if element.kind is not ElementKind.IMAGE:
            continue
        try:
            content_opacity = float(element.content.get("opacity", 1.0))
        except (TypeError, ValueError):
            content_opacity = 1.0
        if float(element.opacity) * content_opacity <= 0.0:
            continue
        clipped = _image_clip(project, layout, element)
        if clipped is not None and _intersection(clipped, layout.back_rect) is not None:
            return True
    return False


def build_export_plan(project: CoverProject) -> CoverExportPlan:
    layout = calculate_layout(project)
    return CoverExportPlan(
        original_size_mm=(layout.bleed_rect.width_mm, layout.bleed_rect.height_mm),
        print_plan=build_print_plan(layout),
        back_cover_blank=not _has_visible_back_image(project, layout),
    )
