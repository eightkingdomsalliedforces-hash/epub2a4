from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .geometry import RectMm
from .models import CoverMetadata
from .typography import points_to_mm

PublisherInfoRole = Literal["heading", "details"]


@dataclass(frozen=True)
class PublisherInfoLine:
    text: str
    role: PublisherInfoRole


@dataclass(frozen=True)
class TextMeasure:
    width_mm: float
    line_height_mm: float


MeasureText = Callable[[str, PublisherInfoRole, float], TextMeasure]


@dataclass(frozen=True)
class PublisherInfoLayout:
    heading_text: str
    detail_lines: tuple[str, ...]
    heading_rect: RectMm | None
    details_rect: RectMm | None
    detail_line_rects: tuple[RectMm, ...]
    heading_font_pt: float
    details_font_pt: float
    details_line_spacing_mm: float
    warnings: tuple[str, ...]

    @property
    def height_mm(self) -> float:
        bottoms = tuple(
            rect.bottom_mm
            for rect in (self.heading_rect, self.details_rect)
            if rect is not None
        )
        tops = tuple(
            rect.y_mm
            for rect in (self.heading_rect, self.details_rect)
            if rect is not None
        )
        return 0.0 if not bottoms else max(bottoms) - min(tops)


def _trimmed(value: object) -> str:
    return str(value or "").strip()


def _prefixed(value: object, label: str) -> str:
    text = _trimmed(value)
    if not text:
        return ""
    normalized = text.replace(":", "：", 1)
    if normalized.startswith(f"{label}："):
        return normalized
    return f"{label}：{text}"


def build_publisher_info_lines(metadata: CoverMetadata) -> tuple[PublisherInfoLine, ...]:
    lines: list[PublisherInfoLine] = []
    publisher = _trimmed(metadata.publisher)
    if publisher:
        lines.append(PublisherInfoLine(publisher, "heading"))
    price = _prefixed(metadata.price, "定價")
    if price:
        lines.append(PublisherInfoLine(price, "details"))
    place = _trimmed(metadata.publication_place)
    if place:
        lines.append(PublisherInfoLine(place, "details"))
    translator = _prefixed(metadata.translator, "譯者")
    if translator:
        lines.append(PublisherInfoLine(translator, "details"))
    return tuple(lines)


def _default_measure(text: str, role: PublisherInfoRole, font_size_pt: float) -> TextMeasure:
    em_mm = points_to_mm(font_size_pt)
    width_units = sum(1.0 if ord(character) > 0xFF else 0.58 for character in text)
    return TextMeasure(width_mm=width_units * em_mm, line_height_mm=em_mm * 1.2)


def _fit_font_size(
    texts: tuple[str, ...],
    role: PublisherInfoRole,
    initial_pt: float,
    min_pt: float,
    max_width_mm: float,
    measure: MeasureText,
) -> float:
    size = float(initial_pt)
    while size > min_pt and any(
        measure(text, role, size).width_mm > max_width_mm for text in texts
    ):
        size = max(min_pt, round(size - 0.25, 2))
    return size


def _wrap_line(
    text: str,
    role: PublisherInfoRole,
    font_size_pt: float,
    max_width_mm: float,
    measure: MeasureText,
) -> tuple[str, ...]:
    if measure(text, role, font_size_pt).width_mm <= max_width_mm:
        return (text,)
    pieces: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and measure(candidate, role, font_size_pt).width_mm > max_width_mm:
            pieces.append(current)
            current = character
        else:
            current = candidate
    if current:
        pieces.append(current)
    return tuple(pieces) or (text,)


def layout_publisher_info(
    *,
    metadata: CoverMetadata,
    x_mm: float,
    y_mm: float,
    max_width_mm: float,
    max_height_mm: float,
    measure: MeasureText | None = None,
    heading_font_pt: float = 10.0,
    details_font_pt: float = 9.0,
    minimum_font_pt: float = 7.5,
    heading_gap_mm: float = 1.0,
) -> PublisherInfoLayout:
    if max_width_mm <= 0.0 or max_height_mm <= 0.0:
        raise ValueError("出版資訊可用範圍必須大於 0。")
    measure_text = measure or _default_measure
    visible = build_publisher_info_lines(metadata)
    heading = next((line.text for line in visible if line.role == "heading"), "")
    details = tuple(line.text for line in visible if line.role == "details")

    fitted_heading_pt = _fit_font_size(
        (heading,) if heading else (),
        "heading",
        heading_font_pt,
        minimum_font_pt,
        max_width_mm,
        measure_text,
    )
    fitted_details_pt = _fit_font_size(
        details,
        "details",
        details_font_pt,
        minimum_font_pt,
        max_width_mm,
        measure_text,
    )

    warnings: list[str] = []
    wrapped_heading = (
        _wrap_line(heading, "heading", fitted_heading_pt, max_width_mm, measure_text)
        if heading
        else ()
    )
    wrapped_details = tuple(
        piece
        for detail in details
        for piece in _wrap_line(
            detail, "details", fitted_details_pt, max_width_mm, measure_text
        )
    )
    if heading and len(wrapped_heading) > 1:
        warnings.append("出版社名稱超出可用寬度，已自動換行。")
    if len(wrapped_details) > len(details):
        warnings.append("出版資訊超出可用寬度，已自動換行。")

    cursor_y = float(y_mm)
    heading_rect: RectMm | None = None
    if wrapped_heading:
        line_height = measure_text("國Ag", "heading", fitted_heading_pt).line_height_mm
        heading_height = line_height * len(wrapped_heading)
        heading_rect = RectMm(float(x_mm), cursor_y, float(max_width_mm), heading_height)
        cursor_y = heading_rect.bottom_mm

    detail_line_rects: list[RectMm] = []
    details_rect: RectMm | None = None
    details_line_spacing_mm = 0.0
    if wrapped_details:
        if heading_rect is not None:
            cursor_y += float(heading_gap_mm)
        line_height = measure_text("國Ag", "details", fitted_details_pt).line_height_mm
        details_line_spacing_mm = line_height * 1.12
        for index, _line in enumerate(wrapped_details):
            line_y = cursor_y + index * details_line_spacing_mm
            detail_line_rects.append(
                RectMm(float(x_mm), line_y, float(max_width_mm), line_height)
            )
        details_height = (
            line_height
            if len(wrapped_details) == 1
            else line_height + (len(wrapped_details) - 1) * details_line_spacing_mm
        )
        details_rect = RectMm(
            float(x_mm), cursor_y, float(max_width_mm), details_height
        )

    result = PublisherInfoLayout(
        heading_text="\n".join(wrapped_heading),
        detail_lines=wrapped_details,
        heading_rect=heading_rect,
        details_rect=details_rect,
        detail_line_rects=tuple(detail_line_rects),
        heading_font_pt=fitted_heading_pt,
        details_font_pt=fitted_details_pt,
        details_line_spacing_mm=details_line_spacing_mm,
        warnings=(),
    )
    if result.height_mm > max_height_mm:
        warnings.append("出版資訊高度超出封底安全區。")
    return PublisherInfoLayout(
        heading_text=result.heading_text,
        detail_lines=result.detail_lines,
        heading_rect=result.heading_rect,
        details_rect=result.details_rect,
        detail_line_rects=result.detail_line_rects,
        heading_font_pt=result.heading_font_pt,
        details_font_pt=result.details_font_pt,
        details_line_spacing_mm=result.details_line_spacing_mm,
        warnings=tuple(warnings),
    )
