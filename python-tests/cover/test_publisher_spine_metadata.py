from __future__ import annotations

import json
from dataclasses import replace

from epub_a4_word.cover.models import CoverMetadata, LogoAssetMetadata
from epub_a4_word.cover.project_io import dumps_project, loads_project


def test_publisher_spine_metadata_round_trips_in_schema_v1(sample_project) -> None:
    logo = LogoAssetMetadata(
        asset_id="publisher-logo",
        path="assets/logo.png",
        source_url="https://example.com/logo.png",
        source_category="official",
        downloaded_at="2026-07-27T08:00:00Z",
        image_format="PNG",
        width_px=640,
        height_px=240,
        license_text="官方網站",
        official_source=True,
        manual_selection=False,
    )
    project = replace(
        sample_project(),
        metadata=replace(
            sample_project().metadata,
            publisher_id="taiwan-kadokawa",
            english_title="A Certain Magical Index",
            volume_number="1",
            arc_label="舊約",
            series_name="電擊文庫",
            internal_book_code="CL0308-17",
            spine_accent_color="#F15A24",
            publisher_logo=logo,
        ),
    )

    loaded = loads_project(dumps_project(project))

    assert loaded.schema_version == 1
    assert loaded.metadata.publisher_id == "taiwan-kadokawa"
    assert loaded.metadata.english_title == "A Certain Magical Index"
    assert loaded.metadata.volume_number == "1"
    assert loaded.metadata.arc_label == "舊約"
    assert loaded.metadata.series_name == "電擊文庫"
    assert loaded.metadata.internal_book_code == "CL0308-17"
    assert loaded.metadata.spine_accent_color == "#F15A24"
    assert loaded.metadata.publisher_logo == logo


def test_old_schema_v1_without_spine_fields_loads_empty_defaults(sample_project) -> None:
    raw = json.loads(dumps_project(sample_project()))
    for key in (
        "publisher_id",
        "english_title",
        "volume_number",
        "arc_label",
        "series_name",
        "internal_book_code",
        "spine_accent_color",
        "publisher_logo",
    ):
        raw["metadata"].pop(key, None)

    loaded = loads_project(json.dumps(raw, ensure_ascii=False))

    assert loaded.metadata.publisher_id == ""
    assert loaded.metadata.english_title == ""
    assert loaded.metadata.volume_number == ""
    assert loaded.metadata.arc_label == ""
    assert loaded.metadata.series_name == ""
    assert loaded.metadata.internal_book_code == ""
    assert loaded.metadata.spine_accent_color == "#F15A24"
    assert loaded.metadata.publisher_logo is None
