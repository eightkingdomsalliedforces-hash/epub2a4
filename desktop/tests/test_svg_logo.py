from __future__ import annotations

from io import BytesIO

from PIL import Image

from epub_a4_word_desktop.cover.svg_logo import rasterize_svg_logo


def test_qt_svg_logo_rasterizer_returns_transparent_png() -> None:
    svg = (
        b"<svg xmlns='http://www.w3.org/2000/svg' width='120' height='40'>"
        b"<rect width='120' height='40' fill='#f15a24'/>"
        b"</svg>"
    )

    payload = rasterize_svg_logo(svg, 120, 40)

    with Image.open(BytesIO(payload)) as image:
        assert image.format == "PNG"
        assert image.size == (2048, 683)
        assert "A" in image.getbands()
