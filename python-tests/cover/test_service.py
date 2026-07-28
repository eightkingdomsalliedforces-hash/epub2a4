from __future__ import annotations

import json
from pathlib import Path

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.service import (
    apply_template,
    export_cover,
    export_cover_bundle,
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
    assert result["metadata"]["embedded_images"][0]["role"] == "front_cover"
    json.dumps(result, ensure_ascii=False)


def test_new_project_uses_working_assets_and_never_writes_beside_source(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    source_parent_before = {path.name for path in source.parent.iterdir()}
    project = loads_project(new_project(str(source), _settings(tmp_path)))

    assert Path(project.working_dir) == (tmp_path / "work").resolve()
    from epub_a4_word.cover.models import ImageMode
    assert project.image_mode is ImageMode.FRONT_ONLY
    image = project.elements_by_id["source-cover-image"]
    image_path = Path(str(image.content["path"]))
    assert image_path.is_file()
    assert image_path.is_relative_to((tmp_path / "work/assets").resolve())
    assert {path.name for path in source.parent.iterdir()} == source_parent_before
    assert project.metadata.title == "測試 EPUB"
    assert project.page_count == 160


def test_new_project_initializes_modern_cover_metadata(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    project = loads_project(
        new_project(
            str(source),
            _settings(
                tmp_path,
                back_highlight_copy="醒目文案",
                spine_style="clean_centered",
                accent_color_mode="manual",
                extracted_accent_color="#D56A31",
            ),
        )
    )

    assert project.metadata.back_vertical_copy == project.metadata.description
    assert project.metadata.back_highlight_copy == "醒目文案"
    assert project.metadata.spine_style == "clean_centered"
    assert project.metadata.accent_color_mode == "manual"
    assert project.metadata.extracted_accent_color == "#D56A31"


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


def test_service_split_exports_share_the_same_two_page_plan(
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
    assert exports["pdf"]["mode"] == exports["docx"]["mode"] == "two_page"
    assert exports["pdf"]["page_count"] == exports["docx"]["page_count"] == 2


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


def test_new_project_uses_separate_embedded_front_and_back_images(
    front_back_epub_factory, tmp_path: Path
) -> None:
    from epub_a4_word.cover.models import ElementKind, ImageMode, Region

    project = loads_project(
        new_project(str(front_back_epub_factory()), _settings(tmp_path))
    )

    assert project.image_mode is ImageMode.SEPARATE_COVERS
    front = project.elements_by_id["source-cover-image"]
    back = project.elements_by_id["source-back-cover-image"]
    assert front.region is Region.FRONT
    assert back.region is Region.BACK
    assert Path(str(front.content["path"])).is_file()
    assert Path(str(back.content["path"])).is_file()
    assert front.content["path"] != back.content["path"]
    assert not any(
        element.kind in {ElementKind.TEXT, ElementKind.BARCODE_PLACEHOLDER}
        for element in project.elements
    )
    assert not any(element.region is Region.SPINE for element in project.elements)


def test_medium_back_cover_candidate_is_not_used_automatically(
    front_back_epub_factory, tmp_path: Path
) -> None:
    from epub_a4_word.cover.models import ImageMode

    project = loads_project(
        new_project(
            str(front_back_epub_factory(generic_back=True)),
            _settings(tmp_path),
        )
    )

    assert project.image_mode is ImageMode.FRONT_ONLY
    assert set(project.elements_by_id) == {"source-cover-image"}


def test_confirmed_medium_back_cover_candidate_is_used(
    front_back_epub_factory, tmp_path: Path
) -> None:
    from epub_a4_word.cover.models import ImageMode, Region

    project = loads_project(
        new_project(
            str(front_back_epub_factory(generic_back=True)),
            _settings(tmp_path, confirmed_back_cover_asset_id="back-image"),
        )
    )

    assert project.image_mode is ImageMode.SEPARATE_COVERS
    assert project.elements_by_id["source-back-cover-image"].region is Region.BACK


def test_source_cover_template_preserves_separate_embedded_covers(
    front_back_epub_factory, tmp_path: Path
) -> None:
    from epub_a4_word.cover.models import ImageMode

    project_json = new_project(str(front_back_epub_factory()), _settings(tmp_path))
    project = loads_project(apply_template(project_json, "minimal"))

    assert project.image_mode is ImageMode.SEPARATE_COVERS
    assert set(project.elements_by_id) == {
        "source-cover-image",
        "source-back-cover-image",
    }


def test_service_exports_original_and_a4_bundle(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    source = fixtures_dir / "cover/metadata.epub"
    project_json = apply_template(
        new_project(
            str(source),
            _settings(tmp_path, trim_width_mm=148.0, trim_height_mm=210.0),
        ),
        "minimal",
    )

    exports = export_cover_bundle(
        project_json,
        str(tmp_path / "original.pdf"),
        str(tmp_path / "print.pdf"),
        str(tmp_path / "print.docx"),
        200,
    )

    assert Path(exports["original_pdf"]["path"]).is_file()
    assert Path(exports["print_pdf"]["path"]).is_file()
    assert Path(exports["print_docx"]["path"]).is_file()
    assert exports["print_plan"]["mode"] == "two_page"
    assert exports["print_plan"]["page_count"] == 2
    assert exports["print_plan"]["back_cover_blank"] is True
