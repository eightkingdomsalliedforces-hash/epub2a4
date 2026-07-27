from __future__ import annotations

from dataclasses import dataclass
import math

from .models import CoverProject
from .project_io import CoverValidationError, validate_project


DEFAULT_SAFE_INSET_MM = 5.0
SPINE_FOLD_SAFE_INSET_MM = 3.0
SPINE_CONTENT_MAX_INSET_MM = 1.0
SPINE_CONTENT_INSET_RATIO = 0.12


class CoverLayoutError(ValueError):
    """Raised when a cover cannot produce valid physical geometry."""


@dataclass(frozen=True)
class RectMm:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    @property
    def right_mm(self) -> float:
        return self.x_mm + self.width_mm

    @property
    def bottom_mm(self) -> float:
        return self.y_mm + self.height_mm

    def to_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x_mm, self.y_mm, self.right_mm, self.bottom_mm)

    def inset(
        self,
        left_mm: float,
        top_mm: float,
        right_mm: float | None = None,
        bottom_mm: float | None = None,
    ) -> "RectMm":
        right = left_mm if right_mm is None else right_mm
        bottom = top_mm if bottom_mm is None else bottom_mm
        width = self.width_mm - left_mm - right
        height = self.height_mm - top_mm - bottom
        if width <= 0.0 or height <= 0.0:
            raise CoverLayoutError("安全區域沒有可用空間。")
        return RectMm(
            self.x_mm + left_mm,
            self.y_mm + top_mm,
            width,
            height,
        )


@dataclass(frozen=True)
class CoverLayout:
    sheet_count: int
    spine_width_mm: float
    spread_rect: RectMm
    bleed_rect: RectMm
    back_rect: RectMm
    spine_rect: RectMm
    front_rect: RectMm
    back_safe_rect: RectMm
    spine_safe_rect: RectMm
    front_safe_rect: RectMm

    # Compatibility aliases make the geometry convenient for template/render code.
    @property
    def back(self) -> RectMm:
        return self.back_rect

    @property
    def spine(self) -> RectMm:
        return self.spine_rect

    @property
    def front(self) -> RectMm:
        return self.front_rect

    @property
    def back_safe(self) -> RectMm:
        return self.back_safe_rect

    @property
    def spine_safe(self) -> RectMm:
        return self.spine_safe_rect

    @property
    def front_safe(self) -> RectMm:
        return self.front_safe_rect


def _spine_safe_rect(spine: RectMm) -> RectMm:
    horizontal_inset = min(
        SPINE_CONTENT_MAX_INSET_MM,
        spine.width_mm * SPINE_CONTENT_INSET_RATIO,
    )
    return spine.inset(
        horizontal_inset,
        DEFAULT_SAFE_INSET_MM,
        horizontal_inset,
        DEFAULT_SAFE_INSET_MM,
    )


def calculate_layout(project: CoverProject) -> CoverLayout:
    """Calculate exact millimetre geometry in back | spine | front order."""

    try:
        validate_project(project)
    except CoverValidationError as exc:
        raise CoverLayoutError(str(exc)) from exc

    sheet_count = math.ceil(project.page_count / 2)
    automatic_spine_mm = sheet_count * float(project.paper_caliper_mm)
    spine_width_mm = (
        float(project.manual_spine_width_mm)
        if project.manual_spine_width_mm is not None
        else automatic_spine_mm
    )
    if not math.isfinite(spine_width_mm) or spine_width_mm <= 0.0:
        raise CoverLayoutError("spine_width_mm 必須大於 0。")

    trim_width_mm = float(project.trim_size.width_mm)
    trim_height_mm = float(project.trim_size.height_mm)
    bleed_mm = float(project.bleed_mm)
    spread_width_mm = trim_width_mm * 2.0 + spine_width_mm

    bleed_rect = RectMm(
        0.0,
        0.0,
        spread_width_mm + 2.0 * bleed_mm,
        trim_height_mm + 2.0 * bleed_mm,
    )
    spread_rect = RectMm(bleed_mm, bleed_mm, spread_width_mm, trim_height_mm)
    back_rect = RectMm(bleed_mm, bleed_mm, trim_width_mm, trim_height_mm)
    spine_rect = RectMm(
        back_rect.right_mm,
        bleed_mm,
        spine_width_mm,
        trim_height_mm,
    )
    front_rect = RectMm(
        spine_rect.right_mm,
        bleed_mm,
        trim_width_mm,
        trim_height_mm,
    )

    back_safe_rect = back_rect.inset(
        DEFAULT_SAFE_INSET_MM,
        DEFAULT_SAFE_INSET_MM,
        SPINE_FOLD_SAFE_INSET_MM,
        DEFAULT_SAFE_INSET_MM,
    )
    front_safe_rect = front_rect.inset(
        SPINE_FOLD_SAFE_INSET_MM,
        DEFAULT_SAFE_INSET_MM,
        DEFAULT_SAFE_INSET_MM,
        DEFAULT_SAFE_INSET_MM,
    )
    spine_safe_rect = _spine_safe_rect(spine_rect)

    return CoverLayout(
        sheet_count=sheet_count,
        spine_width_mm=spine_width_mm,
        spread_rect=spread_rect,
        bleed_rect=bleed_rect,
        back_rect=back_rect,
        spine_rect=spine_rect,
        front_rect=front_rect,
        back_safe_rect=back_safe_rect,
        spine_safe_rect=spine_safe_rect,
        front_safe_rect=front_safe_rect,
    )
