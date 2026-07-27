from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFont


def font_candidates(font_path: str | None) -> tuple[Path, ...]:
    values = (
        font_path,
        os.environ.get("EPUB2A4_DEFAULT_FONT"),
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\mingliu.ttc",
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansCJKtc-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-TC.otf",
    )
    return tuple(Path(value) for value in values if value)


def resolve_font(
    font_family: str,
    font_path: str | None,
    size_px: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Resolve a deterministic local font without network or platform APIs."""

    del font_family  # Family names are advisory; only explicit local paths are portable.
    normalized_size = max(1, int(size_px))
    for candidate in font_candidates(font_path):
        if candidate.is_file():
            try:
                return ImageFont.truetype(candidate, normalized_size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=max(8, normalized_size))
    except TypeError:  # Pillow versions before the scalable default font.
        return ImageFont.load_default()
