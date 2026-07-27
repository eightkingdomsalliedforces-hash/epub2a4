from __future__ import annotations

import json

from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project


def _project(metadata: CoverMetadata) -> CoverProject:
    return CoverProject(
        schema_version=1,
        source_file="book.epub",
        source_type="epub",
        metadata=metadata,
        trim_size=TrimSize(128.0, 182.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
    )


def test_translator_round_trips_without_schema_upgrade() -> None:
    project = _project(CoverMetadata(title="書名", translator="李彥樺"))

    loaded = loads_project(dumps_project(project))

    assert loaded.schema_version == 1
    assert loaded.metadata.translator == "李彥樺"


def test_old_schema_v1_without_translator_loads_empty_string() -> None:
    project = _project(CoverMetadata(title="書名"))
    raw = json.loads(dumps_project(project))
    raw["metadata"].pop("translator", None)

    loaded = loads_project(json.dumps(raw, ensure_ascii=False))

    assert loaded.schema_version == 1
    assert loaded.metadata.translator == ""
