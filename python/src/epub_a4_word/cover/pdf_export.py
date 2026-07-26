from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

from .geometry import calculate_layout
from .models import CoverProject
from .print_plan import build_print_plan
from .render import render_print_page, render_spread


@dataclass(frozen=True)
class ExportResult:
    path: Path
    page_count: int
    mode: Literal["single", "two_page", "original"]
    dpi: int
    warnings: tuple[str, ...] = ()


class CoverExportError(RuntimeError):
    """Raised when an exported PDF does not match its physical print plan."""


def _points_to_mm(points: float) -> float:
    return points / 72.0 * 25.4


def _mm_to_points(mm: float) -> float:
    return mm / 25.4 * 72.0


def _normalize_pdf_boxes(
    output: Path,
    page_sizes_mm: tuple[tuple[float, float], ...],
    *,
    title: str,
    author: str,
) -> None:
    """Rewrite MediaBox values to exact A4 points after raster PDF creation."""

    reader = PdfReader(output)
    if len(reader.pages) != len(page_sizes_mm):
        raise CoverExportError(
            f"PDF 頁數不一致：{len(reader.pages)} != {len(page_sizes_mm)}"
        )
    writer = PdfWriter()
    for page, (width_mm, height_mm) in zip(reader.pages, page_sizes_mm, strict=True):
        exact_box = RectangleObject(
            [0.0, 0.0, _mm_to_points(width_mm), _mm_to_points(height_mm)]
        )
        page.mediabox = exact_box
        page.cropbox = RectangleObject(exact_box)
        page.trimbox = RectangleObject(exact_box)
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": title,
            "/Author": author,
            "/Producer": "epub2a4 cover export",
        }
    )
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("wb") as stream:
            writer.write(stream)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_pdf(
    output: Path,
    page_sizes_mm: tuple[tuple[float, float], ...],
) -> None:
    reader = PdfReader(output)
    if len(reader.pages) != len(page_sizes_mm):
        raise CoverExportError(
            f"PDF 頁數不一致：{len(reader.pages)} != {len(page_sizes_mm)}"
        )
    for index, (page, expected) in enumerate(
        zip(reader.pages, page_sizes_mm, strict=True), start=1
    ):
        actual = (
            _points_to_mm(float(page.mediabox.width)),
            _points_to_mm(float(page.mediabox.height)),
        )
        if any(abs(actual_value - expected_value) > 0.05 for actual_value, expected_value in zip(actual, expected, strict=True)):
            raise CoverExportError(
                f"PDF 第 {index} 頁尺寸不符："
                f"{actual[0]:.3f} × {actual[1]:.3f} mm != "
                f"{expected[0]:.3f} × {expected[1]:.3f} mm"
            )



def export_original_pdf(
    project: CoverProject,
    output_path: Path | str,
    dpi: int = 300,
) -> ExportResult:
    if dpi not in {200, 300}:
        raise ValueError("PDF DPI 只支援 200 或 300。")

    output = Path(output_path)
    if output.suffix.lower() != ".pdf":
        raise ValueError("PDF 輸出路徑必須使用 .pdf 副檔名。")
    output.parent.mkdir(parents=True, exist_ok=True)
    layout = calculate_layout(project)
    image = render_spread(project, dpi).convert("RGB")
    size_mm = ((layout.bleed_rect.width_mm, layout.bleed_rect.height_mm),)
    try:
        image.save(
            output,
            "PDF",
            resolution=float(dpi),
            title=project.metadata.title,
            author=project.metadata.author,
        )
        _normalize_pdf_boxes(
            output,
            size_mm,
            title=project.metadata.title,
            author=project.metadata.author,
        )
        _validate_pdf(output, size_mm)
    except Exception as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, (CoverExportError, ValueError)):
            raise
        raise CoverExportError(f"原始尺寸 PDF 匯出失敗：{exc}") from exc
    finally:
        image.close()

    raw_warnings = project.background.get("warnings", ())
    if isinstance(raw_warnings, (list, tuple)):
        warnings = tuple(str(item) for item in raw_warnings)
    else:
        warnings = (str(raw_warnings),) if raw_warnings else ()
    return ExportResult(output, 1, "original", dpi, warnings)


def export_pdf(
    project: CoverProject,
    output_path: Path | str,
    dpi: int = 300,
) -> ExportResult:
    if dpi not in {200, 300}:
        raise ValueError("PDF DPI 只支援 200 或 300。")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    layout = calculate_layout(project)
    plan = build_print_plan(layout)
    pages = [render_print_page(project, page, dpi).convert("RGB") for page in plan.pages]
    page_sizes_mm = tuple(page.paper_size_mm for page in plan.pages)

    try:
        pages[0].save(
            output,
            "PDF",
            resolution=float(dpi),
            save_all=True,
            append_images=pages[1:],
            title=project.metadata.title,
            author=project.metadata.author,
        )
        _normalize_pdf_boxes(
            output,
            page_sizes_mm,
            title=project.metadata.title,
            author=project.metadata.author,
        )
        _validate_pdf(output, page_sizes_mm)
    except Exception as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, (CoverExportError, ValueError)):
            raise
        raise CoverExportError(f"PDF 匯出失敗：{exc}") from exc
    finally:
        for image in pages:
            image.close()

    raw_warnings = project.background.get("warnings", ())
    if isinstance(raw_warnings, (list, tuple)):
        warnings = tuple(str(item) for item in raw_warnings)
    else:
        warnings = (str(raw_warnings),) if raw_warnings else ()
    return ExportResult(output, len(plan.pages), plan.mode, dpi, warnings)
