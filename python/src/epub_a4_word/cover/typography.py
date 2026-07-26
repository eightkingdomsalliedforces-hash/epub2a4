from __future__ import annotations

import math
from collections.abc import Iterable

MM_PER_INCH = 25.4
POINTS_PER_INCH = 72.0

_FONT_ROLE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "publisher_heading": (
        "DFPYuanW5-GB",
        "DFPYuanW5",
        "DFP Yuan W5",
        "DFYuan-W5",
        "華康中圓體",
        "華康圓體 Std W5",
        "Yuanti TC",
        "PingFang TC",
        "Microsoft JhengHei UI",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "sans-serif",
    ),
    "publisher_details": (
        "DFPYuanW3-GB",
        "DFPYuanW3",
        "DFP Yuan W3",
        "DFYuan-W3",
        "華康細圓體",
        "華康圓體 Std W3",
        "Yuanti TC",
        "PingFang TC",
        "Microsoft JhengHei UI",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "sans-serif",
    ),
    "ocr": (
        "OCR-B",
        "OCR B Std",
        "OCRB",
        "OCR-B 10 BT",
        "Liberation Mono",
        "DejaVu Sans Mono",
        "monospace",
    ),
    "default": (
        "PingFang TC",
        "Microsoft JhengHei UI",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "sans-serif",
    ),
}


def points_to_mm(points: object) -> float:
    """Convert typographic points to millimetres for the Qt scene."""

    try:
        value = float(points)
    except (TypeError, ValueError) as exc:
        raise ValueError("字級必須是數字。") from exc
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("字級必須是大於 0 的有限數字。")
    return value * MM_PER_INCH / POINTS_PER_INCH


def _requested_names(requested: object) -> tuple[str, ...]:
    if requested is None:
        return ()
    if isinstance(requested, str):
        values: Iterable[object] = (requested,)
    elif isinstance(requested, Iterable):
        values = requested
    else:
        values = (requested,)
    return tuple(str(value).strip() for value in values if str(value).strip())


def font_candidates(role: str, requested: object = None) -> tuple[str, ...]:
    """Return ordered, de-duplicated installed-font candidates for a role."""

    normalized_role = str(role or "default").strip().casefold()
    defaults = _FONT_ROLE_CANDIDATES.get(
        normalized_role,
        _FONT_ROLE_CANDIDATES["default"],
    )
    ordered = _requested_names(requested) + defaults
    result: list[str] = []
    seen: set[str] = set()
    for name in ordered:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return tuple(result)
