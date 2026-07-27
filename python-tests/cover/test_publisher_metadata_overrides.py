from __future__ import annotations

import json
from pathlib import Path

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.service import new_project


def test_new_project_accepts_trimmed_publisher_metadata_overrides(
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
        "isbn": " 978-475-752-157-5 ",
        "isbn_addon": " 50110 ",
        "publisher": " 台灣角川 ",
        "price": " NT$110/HK$35 ",
        "publication_place": " 香港代理：角川洲立出版 ",
        "translator": " 李彥樺 ",
    }

    project = loads_project(
        new_project(str(source), json.dumps(settings, ensure_ascii=False))
    )

    assert project.metadata.isbn == "978-475-752-157-5"
    assert project.metadata.isbn_addon == "50110"
    assert project.metadata.publisher == "台灣角川"
    assert project.metadata.price == "NT$110/HK$35"
    assert project.metadata.publication_place == "香港代理：角川洲立出版"
    assert project.metadata.translator == "李彥樺"
