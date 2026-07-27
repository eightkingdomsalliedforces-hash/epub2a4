from __future__ import annotations

import json
from pathlib import Path

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.service import new_project


def test_new_project_uses_trimmed_translator_setting(
    fixtures_dir: Path,
    tmp_path: Path,
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    settings = {
        "working_dir": str(tmp_path / "work"),
        "trim_width_mm": 128.0,
        "trim_height_mm": 182.0,
        "page_count": 160,
        "paper_caliper_mm": 0.10,
        "bleed_mm": 3.0,
        "overlap_mm": 5.0,
        "translator": "  李彥樺  ",
    }

    project = loads_project(
        new_project(str(source), json.dumps(settings, ensure_ascii=False))
    )

    assert project.metadata.translator == "李彥樺"
