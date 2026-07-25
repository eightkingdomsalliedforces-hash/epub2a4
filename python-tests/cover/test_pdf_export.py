from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from pypdf import PdfReader

from epub_a4_word.cover.models import CoverProject
from epub_a4_word.cover.pdf_export import export_pdf


def points_to_mm(points: float) -> float:
    return points / 72.0 * 25.4


def test_single_pdf_is_one_landscape_a4_page(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(105.0, 148.0))
    result = export_pdf(project, tmp_path / "cover.pdf", dpi=300)
    reader = PdfReader(result.path)
    page = reader.pages[0]
    assert result.mode == "single"
    assert result.page_count == 1
    assert len(reader.pages) == 1
    assert points_to_mm(float(page.mediabox.width)) == pytest.approx(297.0, abs=0.05)
    assert points_to_mm(float(page.mediabox.height)) == pytest.approx(210.0, abs=0.05)


def test_split_pdf_has_back_spine_front_order(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(148.0, 210.0))
    result = export_pdf(project, tmp_path / "cover.pdf", dpi=300)
    reader = PdfReader(result.path)
    assert result.mode == "split"
    assert result.page_count == 3
    assert len(reader.pages) == 3
    assert [page.get("/Title") for page in reader.pages] == [None, None, None]
    for page in reader.pages:
        assert points_to_mm(float(page.mediabox.width)) == pytest.approx(210.0, abs=0.05)
        assert points_to_mm(float(page.mediabox.height)) == pytest.approx(297.0, abs=0.05)


def test_pdf_metadata_and_result_fields_are_preserved(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(105.0, 148.0))
    result = export_pdf(project, tmp_path / "nested" / "cover.pdf", dpi=200)
    reader = PdfReader(result.path)
    assert result.path.is_file()
    assert result.dpi == 200
    assert reader.metadata.title == project.metadata.title
    assert reader.metadata.author == project.metadata.author


@pytest.mark.parametrize("dpi", [72, 150, 600])
def test_pdf_rejects_unsupported_dpi(
    sample_project: Callable[..., CoverProject], tmp_path: Path, dpi: int
) -> None:
    output = tmp_path / "cover.pdf"
    with pytest.raises(ValueError, match="200 或 300"):
        export_pdf(sample_project(), output, dpi=dpi)
    assert not output.exists()
