from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from epub_a4_word.cover import service


def test_extract_embedded_epub_asset_to_project_working_directory(
    fixtures_dir: Path,
    tmp_path: Path,
) -> None:
    source = fixtures_dir / "cover" / "metadata.epub"
    project_json = service.new_project(
        str(source),
        json.dumps(
            {
                "working_dir": str(tmp_path / "work"),
                "trim_width_mm": 105.0,
                "trim_height_mm": 148.0,
                "page_count": 160,
                "paper_caliper_mm": 0.10,
                "manual_spine_width_mm": None,
                "bleed_mm": 3.0,
                "overlap_mm": 5.0,
                "dpi": 300,
                "show_crop_marks": True,
                "show_assembly_marks": True,
            }
        ),
    )

    result = service.extract_embedded_asset(project_json, "cover-item")

    extracted = Path(result["path"])
    assert extracted.is_file()
    assert extracted.parent == (tmp_path / "work" / "assets").resolve()
    assert result["asset_id"] == "cover-item"
    with Image.open(extracted) as image:
        assert image.size == (12, 18)
