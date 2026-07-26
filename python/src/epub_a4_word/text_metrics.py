from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ParagraphMetrics:
    line_height_pt: float
    spacing_after_pt: float


def _ceil_half(value: float) -> float:
    return math.ceil(float(value) * 2.0) / 2.0


def paragraph_metrics(
    font_pt: float,
    requested_multiplier: float,
    spacing_after_pt: float,
) -> ParagraphMetrics:
    multiplier = max(float(requested_multiplier), 1.30)
    return ParagraphMetrics(
        line_height_pt=_ceil_half(float(font_pt) * multiplier),
        spacing_after_pt=max(0.0, float(spacing_after_pt)),
    )


_MINIMUM_WORD_SAFETY_PT = {
    "single_a5": 28.0,
    "single_4x6": 28.0,
    "four_up": 24.0,
    "signature16": 24.0,
    "b6_on_a5": 42.0,
}


def word_safety_points(imposition_mode: str, configured_points: float) -> float:
    minimum = _MINIMUM_WORD_SAFETY_PT.get(str(imposition_mode), 24.0)
    return max(float(configured_points), minimum)
