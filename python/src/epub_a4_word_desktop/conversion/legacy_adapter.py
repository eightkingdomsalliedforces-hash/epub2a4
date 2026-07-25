from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from epub_a4_word.converter import ConversionResult, convert_input
from epub_a4_word.pagination import LayoutSettings

ProgressCallback = Callable[[int, str], None]
CancelCheck = Callable[[], bool]


class ConversionCancelled(RuntimeError):
    """Raised when the user cancels a desktop conversion."""


@dataclass(frozen=True)
class LegacyConversionRequest:
    input_path: Path
    output_path: Path
    imposition_mode: str
    margin_mode: str
    font_name: str
    body_font_pt: float
    heading_font_pt: float
    page_numbers: bool
    cut_guides: bool
    output_mark_mode: str = "normal"


def allowed_modes_for_path(path: Path) -> tuple[str, ...]:
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return ("signature16", "four_up", "single_a5", "single_4x6", "b6_on_a5")
    if suffix == ".docx":
        return ("single_a5", "single_4x6")
    return ()


def run_conversion(
    request: LegacyConversionRequest,
    progress: ProgressCallback | None = None,
    cancelled: CancelCheck | None = None,
) -> ConversionResult:
    allowed_modes = allowed_modes_for_path(request.input_path)
    if not allowed_modes:
        raise ValueError("輸入檔案只支援 EPUB 或 DOCX。")
    if request.imposition_mode not in allowed_modes:
        raise ValueError("所選輸出模式不適用於此檔案格式。")
    if request.output_mark_mode not in {"normal", "crop_marks"}:
        raise ValueError("列印標記模式無效。")
    if cancelled is not None and cancelled():
        raise ConversionCancelled("轉換已取消。")

    def report(percent: int, message: str) -> None:
        if cancelled is not None and cancelled():
            raise ConversionCancelled("轉換已取消。")
        if progress is not None:
            progress(percent, message)

    settings = LayoutSettings(
        imposition_mode=request.imposition_mode,
        margin_mode=request.margin_mode,
        font_name=request.font_name,
        body_font_pt=request.body_font_pt,
        heading_font_pt=request.heading_font_pt,
        page_numbers=request.page_numbers,
        cut_guides=request.cut_guides,
        output_mark_mode=request.output_mark_mode,
    )
    return convert_input(
        request.input_path,
        request.output_path,
        settings,
        report,
    )
