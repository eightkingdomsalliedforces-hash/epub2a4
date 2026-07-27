from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .geometry import CoverLayout, RectMm

SpineLayoutTier = Literal["full", "compact", "minimal"]


@dataclass(frozen=True)
class SpineSlot:
    element_id: str
    rect: RectMm
    font_size_pt: float
    role: str
    color: str = "#111111"
    font_weight: int = 400


def spine_layout_tier(width_mm: float) -> SpineLayoutTier:
    if width_mm >= 10.0:
        return "full"
    if width_mm >= 6.0:
        return "compact"
    return "minimal"


def _slice(rect: RectMm, top: float, height: float) -> RectMm:
    return RectMm(
        rect.x_mm,
        rect.y_mm + rect.height_mm * top,
        rect.width_mm,
        rect.height_mm * height,
    )


def build_spine_slots(layout: CoverLayout, accent_color: str) -> tuple[SpineLayoutTier, tuple[SpineSlot, ...]]:
    safe = layout.spine_safe_rect
    tier = spine_layout_tier(layout.spine_rect.width_mm)
    if tier == "full":
        slots = (
            SpineSlot("spine-title-main", _slice(safe, 0.16, 0.42), 8.0, "title", font_weight=600),
            SpineSlot("spine-title-english", _slice(safe, 0.16, 0.26), 4.8, "english", color=accent_color),
            SpineSlot("spine-volume", _slice(safe, 0.54, 0.12), 11.0, "volume", color=accent_color, font_weight=700),
            SpineSlot("spine-arc", _slice(safe, 0.64, 0.08), 5.5, "arc"),
            SpineSlot("spine-author", _slice(safe, 0.72, 0.13), 6.0, "author"),
            SpineSlot("spine-internal-code", _slice(safe, 0.86, 0.05), 4.5, "code"),
            SpineSlot("spine-publisher-name", _slice(safe, 0.91, 0.07), 5.0, "publisher", font_weight=500),
        )
    elif tier == "compact":
        slots = (
            SpineSlot("spine-title-main", _slice(safe, 0.10, 0.52), 7.0, "title", font_weight=600),
            SpineSlot("spine-title-english", _slice(safe, 0.10, 0.30), 4.0, "english", color=accent_color),
            SpineSlot("spine-volume", _slice(safe, 0.60, 0.12), 9.0, "volume", color=accent_color, font_weight=700),
            SpineSlot("spine-author", _slice(safe, 0.72, 0.15), 5.5, "author"),
            SpineSlot("spine-publisher-name", _slice(safe, 0.89, 0.09), 4.5, "publisher", font_weight=500),
        )
    else:
        slots = (
            SpineSlot("spine-title-main", _slice(safe, 0.05, 0.64), 5.5, "title", font_weight=600),
            SpineSlot("spine-volume", _slice(safe, 0.67, 0.13), 7.0, "volume", color=accent_color, font_weight=700),
            SpineSlot("spine-publisher-name", _slice(safe, 0.82, 0.16), 4.0, "publisher", font_weight=500),
        )
    return tier, slots
