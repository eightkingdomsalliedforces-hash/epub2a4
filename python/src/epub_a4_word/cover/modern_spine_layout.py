from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .geometry import CoverLayout, RectMm

ModernSpineTier = Literal["full", "compact", "minimal"]


@dataclass(frozen=True)
class ModernSpineSlot:
    element_id: str
    role: str
    rect: RectMm
    font_size_pt: float
    color: str
    font_weight: int = 400
    direction: str = "vertical"


@dataclass(frozen=True)
class ModernSpineLayout:
    style: str
    tier: ModernSpineTier
    slots: tuple[ModernSpineSlot, ...]
    warnings: tuple[str, ...] = ()


def _tier(width_mm: float) -> ModernSpineTier:
    if width_mm >= 10.0:
        return "full"
    if width_mm >= 6.0:
        return "compact"
    return "minimal"


def _inside(inner: RectMm, outer: RectMm) -> bool:
    return (
        outer.x_mm <= inner.x_mm
        and inner.right_mm <= outer.right_mm
        and outer.y_mm <= inner.y_mm
        and inner.bottom_mm <= outer.bottom_mm
    )


def _rect(
    safe: RectMm,
    top: float,
    height: float,
    *,
    left: float = 0.0,
    width: float = 1.0,
) -> RectMm:
    return RectMm(
        safe.x_mm + safe.width_mm * left,
        safe.y_mm + safe.height_mm * top,
        safe.width_mm * width,
        safe.height_mm * height,
    )


def _font(tier: ModernSpineTier, role: str) -> float:
    scale = {"full": 1.0, "compact": 0.78, "minimal": 0.48}[tier]
    bases = {
        "english_title": 6.0,
        "title": 14.0,
        "arc": 7.0,
        "volume_badge": 12.0,
        "author": 11.0,
        "code": 5.0,
        "publisher": 9.0,
    }
    return max(3.5, round(bases.get(role, 8.0) * scale, 1))


def _slot(
    safe: RectMm,
    tier: ModernSpineTier,
    role: str,
    top: float,
    height: float,
    color: str,
    *,
    left: float = 0.0,
    width: float = 1.0,
    weight: int = 400,
    direction: str = "vertical",
) -> ModernSpineSlot:
    element_names = {
        "logo": "modern-spine-logo",
        "english_title": "modern-spine-english-title",
        "title": "modern-spine-title",
        "arc": "modern-spine-arc",
        "volume_badge": "modern-spine-volume",
        "author": "modern-spine-author",
        "code": "modern-spine-code",
        "publisher": "modern-spine-publisher",
    }
    return ModernSpineSlot(
        element_id=element_names[role],
        role=role,
        rect=_rect(safe, top, height, left=left, width=width),
        font_size_pt=_font(tier, role),
        color=color,
        font_weight=weight,
        direction=direction,
    )


def _reference_slots(
    safe: RectMm,
    tier: ModernSpineTier,
    accent: str,
) -> tuple[ModernSpineSlot, ...]:
    if tier == "full":
        return _reference_full_slots(safe, tier, accent)
    if tier == "compact":
        return _reference_compact_slots(safe, tier, accent)
    return _reference_minimal_slots(safe, tier, accent)


def _reference_full_slots(
    safe: RectMm,
    tier: ModernSpineTier,
    accent: str,
) -> tuple[ModernSpineSlot, ...]:
    return (
        _slot(safe, tier, "logo", 0.00, 0.10, accent),
        _slot(
            safe,
            tier,
            "english_title",
            0.11,
            0.08,
            "#444444",
            direction="horizontal",
        ),
        _slot(safe, tier, "title", 0.20, 0.35, "#191919", weight=700),
        _slot(safe, tier, "arc", 0.56, 0.07, accent, weight=600),
        _slot(safe, tier, "volume_badge", 0.64, 0.09, accent, weight=700),
        _slot(safe, tier, "author", 0.75, 0.11, "#191919", weight=500),
        _slot(
            safe,
            tier,
            "code",
            0.87,
            0.05,
            "#555555",
            width=0.52,
        ),
        _slot(
            safe,
            tier,
            "publisher",
            0.93,
            0.06,
            "#191919",
            weight=500,
        ),
    )


def _reference_compact_slots(
    safe: RectMm,
    tier: ModernSpineTier,
    accent: str,
) -> tuple[ModernSpineSlot, ...]:
    return (
        _slot(safe, tier, "logo", 0.00, 0.10, accent),
        _slot(safe, tier, "title", 0.12, 0.42, "#191919", weight=700),
        _slot(safe, tier, "arc", 0.55, 0.07, accent, weight=600),
        _slot(safe, tier, "volume_badge", 0.64, 0.09, accent, weight=700),
        _slot(safe, tier, "author", 0.75, 0.11, "#191919", weight=500),
        _slot(
            safe,
            tier,
            "code",
            0.875,
            0.05,
            "#555555",
            width=0.58,
        ),
        _slot(
            safe,
            tier,
            "publisher",
            0.94,
            0.055,
            "#191919",
            weight=500,
        ),
    )


def _reference_minimal_slots(
    safe: RectMm,
    tier: ModernSpineTier,
    accent: str,
) -> tuple[ModernSpineSlot, ...]:
    return (
        _slot(safe, tier, "logo", 0.00, 0.11, accent),
        _slot(safe, tier, "title", 0.13, 0.45, "#191919", weight=700),
        _slot(safe, tier, "arc", 0.60, 0.08, accent, weight=600),
        _slot(safe, tier, "volume_badge", 0.70, 0.10, accent, weight=700),
        _slot(safe, tier, "author", 0.82, 0.09, "#191919", weight=500),
        _slot(
            safe,
            tier,
            "publisher",
            0.93,
            0.065,
            "#191919",
            weight=500,
        ),
    )


def _weighted_text_units(text: str) -> float:
    return sum(0.5 if ord(character) < 128 else 1.0 for character in text)


def _text_fits(slot: ModernSpineSlot, text: str, font_size_pt: float) -> bool:
    font_mm = font_size_pt * 25.4 / 72.0
    units = _weighted_text_units(text)
    if slot.direction == "horizontal":
        return units * font_mm * 0.55 <= slot.rect.width_mm
    rows = max(1.0, slot.rect.height_mm / (font_mm * 1.05))
    columns = max(1.0, slot.rect.width_mm / (font_mm * 1.15))
    return units <= rows * columns


def fit_spine_font_size(
    slot: ModernSpineSlot,
    text: str,
) -> tuple[float, tuple[str, ...]]:
    minimums = {
        "title": 6.0,
        "author": 4.5,
        "publisher": 4.0,
        "code": 3.5,
    }
    minimum = minimums.get(slot.role, 3.5)
    fitted = max(minimum, slot.font_size_pt)
    while fitted > minimum and not _text_fits(slot, text, fitted):
        fitted = max(minimum, round(fitted - 0.5, 1))
    if _text_fits(slot, text, fitted):
        return fitted, ()
    return fitted, ("書脊文字已縮至可讀下限並限制於安全範圍。",)


def _clean_slots(
    safe: RectMm,
    tier: ModernSpineTier,
    accent: str,
) -> tuple[ModernSpineSlot, ...]:
    return (
        _slot(safe, tier, "logo", 0.02, 0.12, accent),
        _slot(safe, tier, "title", 0.17, 0.36, "#191919", weight=600),
        _slot(safe, tier, "arc", 0.55, 0.08, "#444444"),
        _slot(safe, tier, "volume_badge", 0.65, 0.10, accent, weight=700),
        _slot(safe, tier, "author", 0.77, 0.12, "#191919", weight=500),
        _slot(safe, tier, "publisher", 0.92, 0.075, "#191919", weight=500),
    )


def _parallel_slots(
    safe: RectMm,
    tier: ModernSpineTier,
    accent: str,
) -> tuple[ModernSpineSlot, ...]:
    return (
        _slot(safe, tier, "logo", 0.00, 0.105, accent),
        _slot(
            safe,
            tier,
            "english_title",
            0.13,
            0.40,
            accent,
            left=0.00,
            width=0.44,
            direction="horizontal",
        ),
        _slot(
            safe,
            tier,
            "title",
            0.13,
            0.40,
            "#191919",
            left=0.50,
            width=0.50,
            weight=600,
        ),
        _slot(safe, tier, "arc", 0.55, 0.075, "#333333"),
        _slot(safe, tier, "volume_badge", 0.64, 0.095, accent, weight=700),
        _slot(safe, tier, "author", 0.75, 0.12, "#191919", weight=500),
        _slot(
            safe,
            tier,
            "code",
            0.88,
            0.045,
            "#555555",
        ),
        _slot(safe, tier, "publisher", 0.935, 0.060, "#191919", weight=500),
    )


def build_modern_spine_slots(
    layout: CoverLayout,
    style: str,
    accent: str,
) -> ModernSpineLayout:
    selected = style
    warnings: tuple[str, ...] = ()
    if selected not in {
        "reference_stacked",
        "clean_centered",
        "parallel_columns",
    }:
        selected = "reference_stacked"
        warnings = ("未知書脊樣式，已改用參考圖堆疊式。",)

    tier = _tier(layout.spine_rect.width_mm)
    safe = layout.spine_safe_rect
    builders = {
        "reference_stacked": _reference_slots,
        "clean_centered": _clean_slots,
        "parallel_columns": _parallel_slots,
    }
    slots = builders[selected](safe, tier, accent)
    if not all(_inside(slot.rect, layout.spine_rect) for slot in slots):
        raise ValueError("書脊元素超出實際書脊範圍。")
    return ModernSpineLayout(
        style=selected,
        tier=tier,
        slots=slots,
        warnings=warnings,
    )
