from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from pypdf import PdfReader

from epub_a4_word.cover.models import CoverProject
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.pdf_export import export_original_pdf, export_pdf
from epub_a4_word.cover.render import mm_to_px


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


def test_split_pdf_has_two_side_pages(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(148.0, 210.0))
    result = export_pdf(project, tmp_path / "cover.pdf", dpi=300)
    reader = PdfReader(result.path)
    assert result.mode == "two_page"
    assert result.page_count == 2
    assert len(reader.pages) == 2
    assert [page.get("/Title") for page in reader.pages] == [None, None]
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


def test_original_pdf_uses_exact_spread_size(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(148.0, 210.0))
    result = export_original_pdf(project, tmp_path / "original.pdf", dpi=300)
    reader = PdfReader(result.path)
    layout = calculate_layout(project)

    assert result.mode == "original"
    assert len(reader.pages) == 1
    assert points_to_mm(float(reader.pages[0].mediabox.width)) == pytest.approx(
        layout.bleed_rect.width_mm, abs=0.05
    )
    assert points_to_mm(float(reader.pages[0].mediabox.height)) == pytest.approx(
        layout.bleed_rect.height_mm, abs=0.05
    )


def test_original_pdf_contains_shared_full_crop_frame(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = sample_project(trim=(105.0, 148.0))
    dpi = 200
    path = export_original_pdf(project, tmp_path / "framed.pdf", dpi=dpi).path
    image = PdfReader(path).pages[0].images[0].image.convert("RGB")
    layout = calculate_layout(project)
    x = mm_to_px(layout.spread_rect.x_mm, dpi)
    y = mm_to_px(
        layout.spread_rect.y_mm + layout.spread_rect.height_mm / 2.0,
        dpi,
    )

    assert max(image.getpixel((x, y))) < 100
