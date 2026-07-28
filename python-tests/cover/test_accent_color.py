from __future__ import annotations

from PIL import Image, ImageDraw

from epub_a4_word.cover.accent_color import apply_auto_accent, extract_accent_color
from epub_a4_word.cover.models import CoverMetadata


def test_extracts_dominant_saturated_colour(tmp_path) -> None:
    path = tmp_path / "cover.png"
    image = Image.new("RGB", (100, 100), "#F7F7F7")
    ImageDraw.Draw(image).rectangle((0, 0, 69, 99), fill="#2674D9")
    image.save(path)

    assert extract_accent_color(path) == "#2674D9"


def test_ignores_black_white_and_gray(tmp_path) -> None:
    path = tmp_path / "cover.png"
    image = Image.new("RGB", (90, 30))
    image.paste("#FFFFFF", (0, 0, 30, 30))
    image.paste("#111111", (30, 0, 60, 30))
    image.paste("#E85D2A", (60, 0, 90, 30))
    image.save(path)

    assert extract_accent_color(path) == "#E85D2A"


def test_manual_accent_is_not_overwritten(tmp_path) -> None:
    metadata = CoverMetadata(
        spine_accent_color="#225588",
        accent_color_mode="manual",
    )

    updated, warnings = apply_auto_accent(metadata, tmp_path / "missing.png")

    assert updated.spine_accent_color == "#225588"
    assert updated.extracted_accent_color == ""
    assert warnings == ()


def test_missing_auto_source_uses_fallback_without_warning() -> None:
    updated, warnings = apply_auto_accent(CoverMetadata(), None)

    assert updated.spine_accent_color == "#F15A24"
    assert updated.extracted_accent_color == "#F15A24"
    assert warnings == ()
