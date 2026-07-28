from __future__ import annotations

import colorsys
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageOps

from .models import CoverMetadata

FALLBACK_ACCENT = "#F15A24"


def _linear_channel(value: int) -> float:
    channel = value / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _white_contrast(rgb: tuple[int, int, int]) -> float:
    red, green, blue = (_linear_channel(value) for value in rgb)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return 1.05 / (luminance + 0.05)


def _ensure_white_contrast(
    rgb: tuple[int, int, int], *, minimum_ratio: float
) -> str:
    red, green, blue = rgb
    hue, saturation, value = colorsys.rgb_to_hsv(
        red / 255.0,
        green / 255.0,
        blue / 255.0,
    )
    adjusted = rgb
    while _white_contrast(adjusted) < minimum_ratio and value > 0:
        value *= 0.92
        adjusted = tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, saturation, value)
        )
    return "#{:02X}{:02X}{:02X}".format(*adjusted)


def extract_accent_color(path: Path | str) -> str:
    with Image.open(path) as source:
        rgb = ImageOps.exif_transpose(source).convert("RGB")
        rgb.thumbnail((128, 128), Image.Resampling.LANCZOS)
        quantized = rgb.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette() or []
        candidates: list[tuple[float, tuple[int, int, int]]] = []
        for count, index in quantized.getcolors() or []:
            start = index * 3
            red, green, blue = palette[start : start + 3]
            _, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0,
                green / 255.0,
                blue / 255.0,
            )
            if saturation < 0.25 or value < 0.18 or value > 0.95:
                continue
            candidates.append(
                (count * (0.5 + saturation), (red, green, blue))
            )
        if not candidates:
            return FALLBACK_ACCENT
        selected = max(candidates, key=lambda item: item[0])[1]
        return _ensure_white_contrast(selected, minimum_ratio=3.0)


def apply_auto_accent(
    metadata: CoverMetadata,
    path: Path | str | None,
) -> tuple[CoverMetadata, tuple[str, ...]]:
    if metadata.accent_color_mode == "manual":
        return metadata, ()
    if path is None:
        return replace(
            metadata,
            spine_accent_color=FALLBACK_ACCENT,
            extracted_accent_color=FALLBACK_ACCENT,
        ), ()
    try:
        color = extract_accent_color(path)
    except (OSError, ValueError) as exc:
        return replace(
            metadata,
            spine_accent_color=FALLBACK_ACCENT,
            extracted_accent_color=FALLBACK_ACCENT,
        ), (f"無法從封面擷取主題色：{exc}",)
    return replace(
        metadata,
        spine_accent_color=color,
        extracted_accent_color=color,
    ), ()
