from __future__ import annotations

from dataclasses import replace
from typing import Callable

from epub_a4_word.cover.models import CoverProject
from epub_a4_word.cover.project_io import dumps_project, loads_project


def test_complete_publisher_metadata_round_trips(
    sample_project: Callable[..., CoverProject],
) -> None:
    project = sample_project()
    metadata = replace(
        project.metadata,
        translator="李彥樺",
        isbn_addon="00110",
        publisher_id="kadokawa-tw",
        english_title="Welcome to the Classroom",
        volume_number="2",
        arc_label="二年級篇",
        series_name="輕小說",
        internal_book_code="CL0308-17",
        spine_accent_color="#F15A24",
    )

    restored = loads_project(dumps_project(replace(project, metadata=metadata)))

    assert restored.metadata.translator == "李彥樺"
    assert restored.metadata.isbn_addon == "00110"
    assert restored.metadata.publisher_id == "kadokawa-tw"
    assert restored.metadata.english_title == "Welcome to the Classroom"
    assert restored.metadata.volume_number == "2"
    assert restored.metadata.arc_label == "二年級篇"
    assert restored.metadata.series_name == "輕小說"
    assert restored.metadata.internal_book_code == "CL0308-17"
    assert restored.metadata.spine_accent_color == "#F15A24"
