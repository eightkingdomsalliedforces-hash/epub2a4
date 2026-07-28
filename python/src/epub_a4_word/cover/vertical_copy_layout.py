from __future__ import annotations

from dataclasses import dataclass
import math

from .geometry import RectMm

_OVERFLOW_WARNING = "封底直排內文超出可用範圍。"


@dataclass(frozen=True)
class VerticalColumn:
    text: str
    rect: RectMm
    font_size_pt: float


@dataclass(frozen=True)
class VerticalCopyLayout:
    columns: tuple[VerticalColumn, ...]
    separators: tuple[RectMm, ...]
    warnings: tuple[str, ...]


def _font_sizes(preferred: float, minimum: float) -> tuple[float, ...]:
    sizes: list[float] = []
    current = preferred
    while current >= minimum:
        sizes.append(round(current, 2))
        current -= 0.5
    if not sizes or sizes[-1] != minimum:
        sizes.append(minimum)
    return tuple(dict.fromkeys(sizes))


def _gaps(preferred: float) -> tuple[float, ...]:
    values: list[float] = []
    current = max(0.8, preferred)
    while current >= 0.8:
        values.append(round(current, 2))
        current -= 0.2
    if not values or values[-1] != 0.8:
        values.append(0.8)
    return tuple(dict.fromkeys(values))


def _split_columns(text: str, capacity: int) -> list[str]:
    columns: list[str] = []
    for forced_column in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not forced_column:
            columns.append("")
            continue
        columns.extend(
            forced_column[start : start + capacity]
            for start in range(0, len(forced_column), capacity)
        )
    return columns


def _place_columns(
    texts: list[str],
    rect: RectMm,
    *,
    font_size_pt: float,
    gap_mm: float,
) -> tuple[tuple[VerticalColumn, ...], tuple[RectMm, ...]] | None:
    font_mm = font_size_pt / 72.0 * 25.4
    column_width = max(font_mm * 1.18, 0.8)
    total_width = len(texts) * column_width + max(0, len(texts) - 1) * gap_mm
    if total_width > rect.width_mm + 1e-9:
        return None

    columns: list[VerticalColumn] = []
    separators: list[RectMm] = []
    for index, text in enumerate(texts):
        x = rect.right_mm - column_width * (index + 1) - gap_mm * index
        columns.append(
            VerticalColumn(
                text=text,
                rect=RectMm(x, rect.y_mm, column_width, rect.height_mm),
                font_size_pt=font_size_pt,
            )
        )
        if index < len(texts) - 1:
            separator_x = x - gap_mm / 2.0 - 0.125
            separators.append(
                RectMm(separator_x, rect.y_mm, 0.25, rect.height_mm)
            )
    return tuple(columns), tuple(separators)


def layout_vertical_copy(
    text: str,
    rect: RectMm,
    *,
    preferred_font_pt: float,
    minimum_font_pt: float,
    preferred_gap_mm: float,
    maximum_columns: int,
) -> VerticalCopyLayout:
    if preferred_font_pt <= 0 or minimum_font_pt <= 0:
        raise ValueError("字級必須大於 0。")
    if preferred_font_pt < minimum_font_pt:
        raise ValueError("偏好字級不可小於最小字級。")
    if maximum_columns < 1:
        raise ValueError("最大欄數必須大於 0。")

    for font_size in _font_sizes(preferred_font_pt, minimum_font_pt):
        font_mm = font_size / 72.0 * 25.4
        capacity = max(1, math.floor(rect.height_mm / font_mm))
        texts = _split_columns(text, capacity)
        if len(texts) > maximum_columns:
            continue
        for gap in _gaps(preferred_gap_mm):
            placed = _place_columns(
                texts,
                rect,
                font_size_pt=font_size,
                gap_mm=gap,
            )
            if placed is not None:
                columns, separators = placed
                return VerticalCopyLayout(columns, separators, ())

    font_size = minimum_font_pt
    font_mm = font_size / 72.0 * 25.4
    capacity = max(1, math.floor(rect.height_mm / font_mm))
    flattened = text.replace("\r", "").replace("\n", "")
    texts = [
        flattened[index * capacity : (index + 1) * capacity]
        for index in range(maximum_columns - 1)
    ]
    texts.append(flattened[(maximum_columns - 1) * capacity :])
    texts = [item for item in texts if item] or [""]
    placed = _place_columns(
        texts,
        rect,
        font_size_pt=font_size,
        gap_mm=0.8,
    )
    if placed is None:
        column_width = max(
            0.5,
            (rect.width_mm - 0.8 * max(0, len(texts) - 1)) / len(texts),
        )
        columns = tuple(
            VerticalColumn(
                text=item,
                rect=RectMm(
                    rect.right_mm - column_width * (index + 1) - 0.8 * index,
                    rect.y_mm,
                    column_width,
                    rect.height_mm,
                ),
                font_size_pt=font_size,
            )
            for index, item in enumerate(texts)
        )
        separators = tuple(
            RectMm(
                columns[index].rect.x_mm - 0.525,
                rect.y_mm,
                0.25,
                rect.height_mm,
            )
            for index in range(len(columns) - 1)
        )
    else:
        columns, separators = placed
    return VerticalCopyLayout(columns, separators, (_OVERFLOW_WARNING,))
