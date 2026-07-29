from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epub_a4_word.converter import ConversionResult
from epub_a4_word.pagination import LayoutSettings

from .legacy_adapter import allowed_modes_for_path

_TRIM_SIZE_BY_MODE: dict[str, tuple[float, float]] = {
    "signature16": (105.0, 148.0),
    "four_up": (105.0, 148.0),
    "single_a5": (148.0, 210.0),
    "single_4x6": (101.6, 152.4),
    "b6_on_a5": (128.0, 182.0),
}
_ALLOWED_MARGINS = {"safe", "maximized", "borderless"}
_ALLOWED_MARK_MODES = {"normal", "crop_marks"}
_ALLOWED_GUIDE_RENDER_MODES = {"vml", "drawingml"}


@dataclass(frozen=True)
class ConversionRequest:
    input_path: Path
    output_path: Path
    imposition_mode: str = "signature16"
    writing_mode: str = "taiwan_vertical"
    binding_direction: str = "right"
    margin_mode: str = "safe"
    font_name: str = "Noto Serif CJK TC"
    body_font_pt: float = 9.0
    heading_font_pt: float = 14.0
    page_numbers: bool = True
    cut_guides: bool = True
    output_mark_mode: str = "normal"
    guide_render_mode: str = "drawingml"
    content_only: bool = True

    def validate(self) -> None:
        source = Path(self.input_path)
        output = Path(self.output_path)
        suffix = source.suffix.lower()
        if not source.is_file():
            raise ValueError("請選擇存在的 EPUB 或 DOCX 檔案。")
        if suffix not in {".epub", ".docx"}:
            raise ValueError("輸入檔案只支援 EPUB 或 DOCX。")
        if output.suffix.lower() != ".docx":
            raise ValueError("輸出檔案必須使用 .docx 副檔名。")
        if not output.parent.is_dir():
            raise ValueError("輸出資料夾不存在。")
        try:
            if source.resolve() == output.resolve():
                raise ValueError("輸出檔案不可覆蓋來源檔案。")
        except OSError:
            pass
        allowed = allowed_modes_for_path(source)
        if self.imposition_mode not in allowed:
            label = "DOCX" if suffix == ".docx" else "EPUB"
            raise ValueError(f"{label} 不支援所選輸出模式。")
        if self.margin_mode not in _ALLOWED_MARGINS:
            raise ValueError("邊界模式無效。")
        if self.writing_mode not in {"taiwan_vertical", "horizontal"}:
            raise ValueError("正文方向無效。")
        if self.binding_direction not in {"right", "left"}:
            raise ValueError("裝訂方向無效。")
        if self.output_mark_mode not in _ALLOWED_MARK_MODES:
            raise ValueError("輸出標記模式無效。")
        if self.imposition_mode != "b6_on_a5" and self.output_mark_mode != "normal":
            raise ValueError("只有 B6 內容置於 A5 紙張模式支援裁切標記。")
        if self.guide_render_mode not in _ALLOWED_GUIDE_RENDER_MODES:
            raise ValueError("裁切線相容模式無效。")
        if not self.font_name.strip():
            raise ValueError("字型名稱不可為空。")
        if self.body_font_pt <= 0 or self.heading_font_pt <= 0:
            raise ValueError("字級必須大於 0。")

    def to_layout_settings(self) -> LayoutSettings:
        return LayoutSettings(
            imposition_mode=self.imposition_mode,
            writing_mode=self.writing_mode,
            binding_direction=self.binding_direction,
            margin_mode=self.margin_mode,
            font_name=self.font_name.strip(),
            body_font_pt=float(self.body_font_pt),
            heading_font_pt=float(self.heading_font_pt),
            page_numbers=bool(self.page_numbers),
            cut_guides=bool(self.cut_guides),
            output_mark_mode=self.output_mark_mode,
            guide_render_mode=self.guide_render_mode,
        )


@dataclass(frozen=True)
class ConversionCompletion:
    source: Path
    output_path: Path
    actual_page_count: int
    trim_size_mm: tuple[float, float]
    title: str
    author: str
    warnings: tuple[str, ...]
    imposition_mode: str

    def to_cover_payload(self) -> dict[str, object]:
        width_mm, height_mm = self.trim_size_mm
        return {
            "source_path": str(self.source),
            "output_path": str(self.output_path),
            "page_count": self.actual_page_count,
            "trim_size_mm": {"width_mm": width_mm, "height_mm": height_mm},
            "title": self.title,
            "author": self.author,
        }


def trim_size_for_mode(imposition_mode: str) -> tuple[float, float]:
    try:
        return _TRIM_SIZE_BY_MODE[imposition_mode]
    except KeyError as exc:
        raise ValueError(f"未知輸出模式：{imposition_mode}") from exc


def make_completion(request: ConversionRequest, result: ConversionResult) -> ConversionCompletion:
    return ConversionCompletion(
        source=Path(request.input_path),
        output_path=Path(result.output_path),
        actual_page_count=int(result.mini_page_count),
        trim_size_mm=trim_size_for_mode(result.imposition_mode),
        title=result.title,
        author=result.author,
        warnings=tuple(result.warnings),
        imposition_mode=result.imposition_mode,
    )


def completion_payload(request: ConversionRequest, result: ConversionResult) -> dict[str, Any]:
    return dict(make_completion(request, result).to_cover_payload())
