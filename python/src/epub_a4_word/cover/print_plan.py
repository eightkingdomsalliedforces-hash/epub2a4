from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .geometry import CoverLayout, CoverLayoutError, RectMm


A4_PORTRAIT = (210.0, 297.0)
A4_LANDSCAPE = (297.0, 210.0)
_TOLERANCE_MM = 1e-9


@dataclass(frozen=True)
class PrintMark:
    kind: Literal["line", "label"]
    x1_mm: float
    y1_mm: float
    x2_mm: float | None = None
    y2_mm: float | None = None
    label: str = ""


@dataclass(frozen=True)
class PrintPage:
    name: str
    orientation: Literal["portrait", "landscape"]
    paper_size_mm: tuple[float, float]
    source_rect: RectMm
    destination_rect: RectMm
    scale: float
    left_overlap_mm: float = 0.0
    right_overlap_mm: float = 0.0
    marks: tuple[PrintMark, ...] = ()

    @property
    def page_size_mm(self) -> tuple[float, float]:
        return self.paper_size_mm


@dataclass(frozen=True)
class PrintPlan:
    mode: Literal["single", "split"]
    pages: tuple[PrintPage, ...]


def _fits(source: RectMm, paper: tuple[float, float]) -> bool:
    return (
        source.width_mm <= paper[0] + _TOLERANCE_MM
        and source.height_mm <= paper[1] + _TOLERANCE_MM
    )


def _centered_destination(source: RectMm, paper: tuple[float, float]) -> RectMm:
    return RectMm(
        (paper[0] - source.width_mm) / 2.0,
        (paper[1] - source.height_mm) / 2.0,
        source.width_mm,
        source.height_mm,
    )


def _choose_orientation(source: RectMm) -> tuple[str, tuple[float, float]]:
    candidates: list[tuple[float, str, tuple[float, float]]] = []
    for orientation, paper in (
        ("portrait", A4_PORTRAIT),
        ("landscape", A4_LANDSCAPE),
    ):
        if _fits(source, paper):
            horizontal_margin = (paper[0] - source.width_mm) / 2.0
            vertical_margin = (paper[1] - source.height_mm) / 2.0
            candidates.append((min(horizontal_margin, vertical_margin), orientation, paper))
    if not candidates:
        raise CoverLayoutError(
            f"列印裁片 {source.width_mm:.3f} × {source.height_mm:.3f} mm "
            "無法以 1:1 放入 A4。"
        )
    # Prefer the larger minimum margin; use portrait as deterministic tie-breaker.
    candidates.sort(key=lambda item: (item[0], item[1] == "portrait"), reverse=True)
    _, orientation, paper = candidates[0]
    return orientation, paper


def _point_in_source(x_mm: float, y_mm: float, source: RectMm) -> bool:
    return (
        source.x_mm - _TOLERANCE_MM <= x_mm <= source.right_mm + _TOLERANCE_MM
        and source.y_mm - _TOLERANCE_MM <= y_mm <= source.bottom_mm + _TOLERANCE_MM
    )


def _to_page_point(
    x_mm: float,
    y_mm: float,
    source: RectMm,
    destination: RectMm,
) -> tuple[float, float]:
    return (
        destination.x_mm + (x_mm - source.x_mm),
        destination.y_mm + (y_mm - source.y_mm),
    )


def _build_marks(
    layout: CoverLayout,
    source: RectMm,
    destination: RectMm,
    label: str,
) -> tuple[PrintMark, ...]:
    marks: list[PrintMark] = []
    trim_corners = (
        (layout.back_rect.x_mm, layout.back_rect.y_mm),
        (layout.back_rect.right_mm, layout.back_rect.y_mm),
        (layout.back_rect.x_mm, layout.back_rect.bottom_mm),
        (layout.back_rect.right_mm, layout.back_rect.bottom_mm),
        (layout.spine_rect.x_mm, layout.spine_rect.y_mm),
        (layout.spine_rect.right_mm, layout.spine_rect.y_mm),
        (layout.spine_rect.x_mm, layout.spine_rect.bottom_mm),
        (layout.spine_rect.right_mm, layout.spine_rect.bottom_mm),
        (layout.front_rect.x_mm, layout.front_rect.y_mm),
        (layout.front_rect.right_mm, layout.front_rect.y_mm),
        (layout.front_rect.x_mm, layout.front_rect.bottom_mm),
        (layout.front_rect.right_mm, layout.front_rect.bottom_mm),
    )
    seen: set[tuple[float, float]] = set()
    mark_length = 3.0
    for x_mm, y_mm in trim_corners:
        key = (round(x_mm, 9), round(y_mm, 9))
        if key in seen or not _point_in_source(x_mm, y_mm, source):
            continue
        seen.add(key)
        page_x, page_y = _to_page_point(x_mm, y_mm, source, destination)
        vertical_direction = -1.0 if y_mm <= layout.spread_rect.y_mm else 1.0
        horizontal_direction = -1.0 if x_mm <= layout.spread_rect.x_mm else 1.0
        marks.append(
            PrintMark(
                "line",
                page_x,
                page_y,
                page_x,
                page_y + vertical_direction * mark_length,
            )
        )
        marks.append(
            PrintMark(
                "line",
                page_x,
                page_y,
                page_x + horizontal_direction * mark_length,
                page_y,
            )
        )

    label_y = max(3.0, destination.y_mm - 5.0)
    marks.append(
        PrintMark(
            "label",
            destination.x_mm + destination.width_mm / 2.0,
            label_y,
            label=label,
        )
    )
    return tuple(marks)


def _page(
    *,
    name: str,
    source: RectMm,
    layout: CoverLayout,
    left_overlap_mm: float = 0.0,
    right_overlap_mm: float = 0.0,
    force_landscape: bool = False,
) -> PrintPage:
    if force_landscape:
        orientation = "landscape"
        paper = A4_LANDSCAPE
        if not _fits(source, paper):
            raise CoverLayoutError("完整封面無法以 1:1 放入橫向 A4。")
    else:
        orientation, paper = _choose_orientation(source)
    destination = _centered_destination(source, paper)
    return PrintPage(
        name=name,
        orientation=orientation,  # type: ignore[arg-type]
        paper_size_mm=paper,
        source_rect=source,
        destination_rect=destination,
        scale=1.0,
        left_overlap_mm=left_overlap_mm,
        right_overlap_mm=right_overlap_mm,
        marks=_build_marks(layout, source, destination, name),
    )


def build_print_plan(layout: CoverLayout) -> PrintPlan:
    """Build an exact 1:1 A4 plan without ever scaling the finished cover."""

    if _fits(layout.bleed_rect, A4_LANDSCAPE):
        return PrintPlan(
            mode="single",
            pages=(
                _page(
                    name="spread",
                    source=layout.bleed_rect,
                    layout=layout,
                    force_landscape=True,
                ),
            ),
        )

    overlap_mm = 5.0
    actual_back_overlap = min(overlap_mm, layout.spine_rect.width_mm)
    back_source = RectMm(
        layout.bleed_rect.x_mm,
        layout.bleed_rect.y_mm,
        layout.spine_rect.x_mm + actual_back_overlap - layout.bleed_rect.x_mm,
        layout.bleed_rect.height_mm,
    )

    spine_left = max(layout.back_rect.x_mm, layout.spine_rect.x_mm - overlap_mm)
    spine_right = min(layout.front_rect.right_mm, layout.spine_rect.right_mm + overlap_mm)
    spine_source = RectMm(
        spine_left,
        layout.bleed_rect.y_mm,
        spine_right - spine_left,
        layout.bleed_rect.height_mm,
    )
    actual_left_overlap = layout.spine_rect.x_mm - spine_left
    actual_right_overlap = spine_right - layout.spine_rect.right_mm

    actual_front_overlap = min(overlap_mm, layout.spine_rect.width_mm)
    front_left = layout.spine_rect.right_mm - actual_front_overlap
    front_source = RectMm(
        front_left,
        layout.bleed_rect.y_mm,
        layout.bleed_rect.right_mm - front_left,
        layout.bleed_rect.height_mm,
    )

    return PrintPlan(
        mode="split",
        pages=(
            _page(
                name="back",
                source=back_source,
                layout=layout,
                right_overlap_mm=actual_back_overlap,
            ),
            _page(
                name="spine",
                source=spine_source,
                layout=layout,
                left_overlap_mm=actual_left_overlap,
                right_overlap_mm=actual_right_overlap,
            ),
            _page(
                name="front",
                source=front_source,
                layout=layout,
                left_overlap_mm=actual_front_overlap,
            ),
        ),
    )
