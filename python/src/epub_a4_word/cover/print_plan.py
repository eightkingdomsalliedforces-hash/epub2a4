from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .geometry import CoverLayout, CoverLayoutError, RectMm
from .models import CoverProject


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
    role: Literal["crop", "alignment", "overlap", "label", "instruction"] = "crop"
    line_style: Literal["solid", "dashed", "dotted"] = "solid"


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
    mode: Literal["single", "two_page"]
    pages: tuple[PrintPage, ...]


def visible_print_marks(
    project: CoverProject,
    page: PrintPage,
) -> tuple[PrintMark, ...]:
    """Return only print marks enabled by the shared export settings."""

    marks = page.marks
    if not project.export_settings.show_crop_marks:
        marks = tuple(mark for mark in marks if mark.role != "crop")
    if not project.export_settings.show_assembly_marks:
        marks = tuple(
            mark
            for mark in marks
            if mark.role not in {"alignment", "overlap", "label", "instruction"}
        )
    return marks


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
            "無法以 1:1 放入 A4；已停用自動縮放。"
        )
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


def _outside_label_y(destination: RectMm, paper_height_mm: float) -> float:
    if destination.y_mm >= 8.0:
        return destination.y_mm - 5.0
    if paper_height_mm - destination.bottom_mm >= 8.0:
        return destination.bottom_mm + 5.0
    return max(1.5, destination.y_mm - 1.5)


def _build_marks(
    layout: CoverLayout,
    source: RectMm,
    destination: RectMm,
    paper: tuple[float, float],
    label: str,
    *,
    instruction: str = "",
    overlap_start_mm: float | None = None,
    overlap_end_mm: float | None = None,
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
                role="crop",
            )
        )
        marks.append(
            PrintMark(
                "line",
                page_x,
                page_y,
                page_x + horizontal_direction * mark_length,
                page_y,
                role="crop",
            )
        )

    label_y = _outside_label_y(destination, paper[1])
    marks.append(
        PrintMark(
            "label",
            destination.x_mm + destination.width_mm / 2.0,
            label_y,
            label=label,
            role="label",
        )
    )
    if instruction:
        instruction_y = (
            label_y - 4.0
            if label_y < destination.y_mm
            else label_y + 4.0
        )
        marks.append(
            PrintMark(
                "label",
                destination.x_mm + destination.width_mm / 2.0,
                instruction_y,
                label=instruction,
                role="instruction",
            )
        )

    overlap_values = tuple(
        value
        for value in (overlap_start_mm, overlap_end_mm)
        if value is not None and source.x_mm <= value <= source.right_mm
    )
    for value in overlap_values:
        x, top = _to_page_point(value, source.y_mm, source, destination)
        _, bottom = _to_page_point(value, source.bottom_mm, source, destination)
        marks.append(
            PrintMark(
                "line",
                x,
                top,
                x,
                bottom,
                role="overlap",
                line_style="dashed",
            )
        )
    if len(overlap_values) == 2:
        center = sum(overlap_values) / 2.0
        x, _ = _to_page_point(center, source.y_mm, source, destination)
        overlap_label_y = (
            label_y - 8.0
            if label_y < destination.y_mm
            else label_y + 8.0
        )
        marks.append(
            PrintMark(
                "label",
                x,
                overlap_label_y,
                label="重疊黏貼區",
                role="overlap",
                line_style="dashed",
            )
        )
    return tuple(marks)


def _page(
    *,
    name: str,
    source: RectMm,
    layout: CoverLayout,
    label: str,
    instruction: str = "",
    left_overlap_mm: float = 0.0,
    right_overlap_mm: float = 0.0,
    overlap_start_mm: float | None = None,
    overlap_end_mm: float | None = None,
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
        marks=_build_marks(
            layout,
            source,
            destination,
            paper,
            label,
            instruction=instruction,
            overlap_start_mm=overlap_start_mm,
            overlap_end_mm=overlap_end_mm,
        ),
    )


def _two_page_sources(
    layout: CoverLayout,
    total_overlap_mm: float,
) -> tuple[RectMm, RectMm]:
    overlap_each_side = total_overlap_mm / 2.0
    spine_center = layout.spine_rect.x_mm + layout.spine_rect.width_mm / 2.0
    back_right = min(layout.bleed_rect.right_mm, spine_center + overlap_each_side)
    front_left = max(layout.bleed_rect.x_mm, spine_center - overlap_each_side)
    return (
        RectMm(
            layout.bleed_rect.x_mm,
            layout.bleed_rect.y_mm,
            back_right - layout.bleed_rect.x_mm,
            layout.bleed_rect.height_mm,
        ),
        RectMm(
            front_left,
            layout.bleed_rect.y_mm,
            layout.bleed_rect.right_mm - front_left,
            layout.bleed_rect.height_mm,
        ),
    )


def build_print_plan(layout: CoverLayout) -> PrintPlan:
    """Build an exact 1:1 A4 plan without scaling the finished cover."""

    if _fits(layout.bleed_rect, A4_LANDSCAPE):
        return PrintPlan(
            mode="single",
            pages=(
                _page(
                    name="spread",
                    source=layout.bleed_rect,
                    layout=layout,
                    label="完整書衣",
                    instruction="100% 實際大小列印，請關閉「符合紙張大小」",
                    force_landscape=True,
                ),
            ),
        )

    failure_dimensions: tuple[RectMm, RectMm] | None = None
    total_overlap = 10.0
    while total_overlap >= 5.0 - _TOLERANCE_MM:
        back_source, front_source = _two_page_sources(layout, total_overlap)
        failure_dimensions = (back_source, front_source)
        try:
            _choose_orientation(back_source)
            _choose_orientation(front_source)
        except CoverLayoutError:
            total_overlap -= 0.5
            continue
        overlap_each_side = total_overlap / 2.0
        overlap_start = front_source.x_mm
        overlap_end = back_source.right_mm
        return PrintPlan(
            mode="two_page",
            pages=(
                _page(
                    name="back_side",
                    source=back_source,
                    layout=layout,
                    label="第 1 頁／2：封底側",
                    instruction="100% 實際大小列印，請關閉「符合紙張大小」",
                    right_overlap_mm=overlap_each_side,
                    overlap_start_mm=overlap_start,
                    overlap_end_mm=overlap_end,
                ),
                _page(
                    name="front_side",
                    source=front_source,
                    layout=layout,
                    label="第 2 頁／2：正面側",
                    instruction="100% 實際大小列印，請關閉「符合紙張大小」",
                    left_overlap_mm=overlap_each_side,
                    overlap_start_mm=overlap_start,
                    overlap_end_mm=overlap_end,
                ),
            ),
        )

    assert failure_dimensions is not None
    back_source, front_source = failure_dimensions
    raise CoverLayoutError(
        "封面無法在不縮放的情況下拆成兩張 A4："
        f"封底側 {back_source.width_mm:.3f} × {back_source.height_mm:.3f} mm，"
        f"正面側 {front_source.width_mm:.3f} × {front_source.height_mm:.3f} mm；"
        "自動縮放已停用。"
    )
