from __future__ import annotations

import json
from pathlib import Path

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.service import (
    apply_template,
    export_cover,
    inspect_source,
    new_project,
    render_preview,
)


def _settings(tmp_path: Path, **overrides: object) -> str:
    values: dict[str, object] = {
        "working_dir": str(tmp_path / "work"),
        "trim_width_mm": 105.0,
        "trim_height_mm": 148.0,
        "page_count": 160,
        "paper_caliper_mm": 0.10,
        "bleed_mm": 3.0,
        "overlap_mm": 5.0,
    }
    values.update(overrides)
    return json.dumps(values, ensure_ascii=False)


def test_inspect_source_returns_json_safe_metadata(fixtures_dir: Path) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    result = inspect_source(str(source))
    assert result["source_type"] == "epub"
    assert result["metadata"]["title"] == "測試 EPUB"
    assert result["metadata"]["embedded_images"][0]["role"] == "cover"
    json.dumps(result, ensure_ascii=False)


def test_new_project_uses_working_assets_and_never_writes_beside_source(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    source_parent_before = {path.name for path in source.parent.iterdir()}
    project = loads_project(new_project(str(source), _settings(tmp_path)))

    assert Path(project.working_dir) == (tmp_path / "work").resolve()
    image = project.elements_by_id["source-cover-image"]
    image_path = Path(str(image.content["path"]))
    assert image_path.is_file()
    assert image_path.is_relative_to((tmp_path / "work/assets").resolve())
    assert {path.name for path in source.parent.iterdir()} == source_parent_before
    assert project.metadata.title == "測試 EPUB"
    assert project.page_count == 160


def test_new_project_estimates_epub_pages_when_not_supplied(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    settings = json.loads(_settings(tmp_path))
    settings.pop("page_count")
    project = loads_project(new_project(str(source), json.dumps(settings)))
    assert project.page_count >= 1
    assert project.metadata.page_count_is_estimate is True


def test_service_creates_preview_and_both_exports(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    project_json = new_project(str(source), _settings(tmp_path))
    project_json = apply_template(project_json, "minimal_text")

    preview = render_preview(project_json, str(tmp_path / "preview.png"), 900)
    exports = export_cover(
        project_json,
        str(tmp_path / "cover.pdf"),
        str(tmp_path / "cover.docx"),
        300,
    )

    assert max(preview["width_px"], preview["height_px"]) <= 900
    assert Path(preview["path"]).is_file()
    assert Path(exports["pdf"]["path"]).is_file()
    assert Path(exports["docx"]["path"]).is_file()
    assert exports["pdf"]["page_count"] == exports["docx"]["page_count"] == 1


def test_service_split_exports_share_the_same_three_page_plan(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    project_json = new_project(
        str(source),
        _settings(tmp_path, trim_width_mm=148.0, trim_height_mm=210.0),
    )
    exports = export_cover(
        apply_template(project_json, "full_spread"),
        str(tmp_path / "split.pdf"),
        str(tmp_path / "split.docx"),
        200,
    )
    assert exports["pdf"]["mode"] == exports["docx"]["mode"] == "split"
    assert exports["pdf"]["page_count"] == exports["docx"]["page_count"] == 3


def test_new_project_rejects_missing_working_dir(fixtures_dir: Path) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    settings = json.dumps({
        "trim_width_mm": 105.0,
        "trim_height_mm": 148.0,
        "page_count": 10,
        "paper_caliper_mm": 0.1,
        "bleed_mm": 3.0,
        "overlap_mm": 5.0,
    })
    try:
        new_project(str(source), settings)
    except ValueError as exc:
        assert "working_dir" in str(exc)
    else:
        raise AssertionError("missing working_dir must be rejected")
