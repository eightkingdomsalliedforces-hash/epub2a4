from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from epub_a4_word.cover.models import LogoAssetMetadata
from epub_a4_word.cover.render import render_spread
from epub_a4_word.cover.templates import apply_template


# This regression test also verifies platforms without a native CairoSVG runtime.
def test_combined_template_renders_safe_svg_publisher_logo(sample_project, tmp_path: Path) -> None:
    logo = tmp_path / "logo.svg"
    logo.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='40'>"
        "<rect width='120' height='40' fill='#f15a24'/>"
        "</svg>",
        "utf-8",
    )
    project = replace(
        sample_project(manual_spine_width_mm=12.0),
        metadata=replace(
            sample_project().metadata,
            publisher="台灣角川",
            publisher_logo=LogoAssetMetadata(
                asset_id="logo",
                path=str(logo),
                image_format="SVG",
                width_px=120,
                height_px=40,
            ),
        ),
    )
    templated = apply_template(project, "publisher_back_matter_with_spine")

    image = render_spread(templated, 72)

    assert image.width > 0
    assert image.height > 0
