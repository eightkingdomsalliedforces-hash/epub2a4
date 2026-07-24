from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFont


def resolve_font(
    font_family: str,
    font_path: str | None,
    size_px: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Resolve a deterministic local font without network or platform APIs."""

    del font_family  # Family names are advisory; only explicit local paths are portable.
    normalized_size = max(1, int(size_px))
    candidates = (font_path, os.environ.get("EPUB2A4_DEFAULT_FONT"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, normalized_size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=max(8, normalized_size))
    except TypeError:  # Pillow versions before the scalable default font.
        return ImageFont.load_default()
