from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image

from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word.cover.search.logo_download import import_logo_file
from epub_a4_word.cover.search.logo_models import LogoCandidate, LogoSourceCategory
from epub_a4_word.cover.templates import apply_template
from epub_a4_word_desktop.cover.controller import CoverController


def _project(tmp_path: Path) -> CoverProject:
    source = tmp_path / "book.epub"
    source.write_bytes(b"fixture")
    return CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="魔法禁書目錄", author="鎌池和馬", publisher="台灣角川"),
        trim_size=TrimSize(128.0, 182.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=12.0,
        bleed_mm=0.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path / "work"),
    )


def test_controller_embeds_selected_logo_and_refreshes_spine(tmp_path: Path) -> None:
    source = tmp_path / "logo.png"
    Image.new("RGBA", (120, 40), (255, 0, 0, 0)).save(source)
    project = apply_template(_project(tmp_path), "publisher_back_matter_with_spine")
    controller = CoverController(working_dir=tmp_path / "work", auto_preview=False)
    controller.replace_project(dumps_project(project), clear_history=True)
    downloaded = import_logo_file(source, tmp_path / "validated")
    candidate = LogoCandidate(
        provider="official",
        candidate_id="logo",
        title="台灣角川 Logo",
        image_url="https://www.kadokawa.com.tw/logo.png",
        preview_url="",
        source_page="https://www.kadokawa.com.tw/",
        source_category=LogoSourceCategory.OFFICIAL,
        source_domain="kadokawa.com.tw",
        license_text="官方網站",
        official_source=True,
    )

    asset_id = controller.apply_publisher_logo(downloaded, candidate)
    updated = loads_project(controller.project_json)

    assert asset_id.startswith("publisher-logo-")
    assert updated.metadata.publisher_logo is not None
    assert Path(updated.metadata.publisher_logo.path).is_file()
    assert updated.metadata.publisher_logo.official_source is True
    assert updated.elements_by_id["spine-publisher-logo"].content["fit"] == "contain"

    asset_id = controller.apply_manual_publisher_logo(source)
    updated = loads_project(controller.project_json)

    assert asset_id.startswith("publisher-logo-")
    assert updated.metadata.publisher_logo is not None
    assert updated.metadata.publisher_logo.manual_selection is True
    assert Path(updated.metadata.publisher_logo.path).suffix == ".png"
