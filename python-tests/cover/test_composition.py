from __future__ import annotations

from PIL import Image

from epub_a4_word.cover.composition import CompositionSelection, compose_full_spread
from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.search.models import CandidateCategory


def test_composition_uses_back_spine_front_print_order(tmp_path):
    paths = {}
    for name, color in {
        "back": (255, 0, 0),
        "spine": (0, 255, 0),
        "front": (0, 0, 255),
    }.items():
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (100, 150), color).save(path)
        paths[name] = path

    project = CoverProject(
        schema_version=1,
        source_file=str(tmp_path / "book.epub"),
        source_type="epub",
        metadata=CoverMetadata(title="範例書"),
        trim_size=TrimSize(128.0, 182.0),
        page_count=100,
        paper_caliper_mm=0.1,
        manual_spine_width_mm=10.0,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path),
    )
    output = tmp_path / "spread.png"
    compose_full_spread(
        project,
        {
            CandidateCategory.BACK: CompositionSelection(paths["back"], CandidateCategory.BACK),
            CandidateCategory.SPINE: CompositionSelection(paths["spine"], CandidateCategory.SPINE),
            CandidateCategory.FRONT: CompositionSelection(paths["front"], CandidateCategory.FRONT),
        },
        output,
        dpi=100,
    )

    image = Image.open(output).convert("RGB")
    width, height = image.size
    assert image.getpixel((int(width * 0.20), height // 2))[0] > 200
    assert image.getpixel((width // 2, height // 2))[1] > 200
    assert image.getpixel((int(width * 0.80), height // 2))[2] > 200
