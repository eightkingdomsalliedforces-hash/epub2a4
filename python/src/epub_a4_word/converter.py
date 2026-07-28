from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable

from PIL import Image

from .docx_writer import write_docx
from .imposition import build_imposition
from .epub import parse_epub
from .models import ImageBlock
from .pagination import LayoutSettings, paginate

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    title: str
    author: str
    mini_page_count: int
    a4_page_count: int
    image_count: int
    warnings: tuple[str, ...]
    imposition_mode: str
    paper_sheet_count: int
    signature_count: int
    padded_mini_page_count: int
    source_format: str = "epub"


def _notify(progress: ProgressCallback | None, percent: int, message: str) -> None:
    if progress is not None:
        progress(percent, message)


def _image_size(data: bytes, media_type: str, path: str) -> tuple[int, int]:
    if media_type == "image/svg+xml" or Path(path).suffix.lower() == ".svg":
        try:
            import cairosvg
        except (ImportError, OSError) as exc:
            raise ValueError("SVG 圖片需要額外安裝 CairoSVG 與其系統元件") from exc
        data = cairosvg.svg2png(bytestring=data)
    with Image.open(BytesIO(data)) as image:
        image.load()
        return image.size


def convert_epub(
    input_path: Path | str,
    output_path: Path | str,
    settings: LayoutSettings | None = None,
    progress: ProgressCallback | None = None,
    *,
    content_only: bool = True,
    confirmed_back_cover_page: str | None = None,
) -> ConversionResult:
    settings = settings or LayoutSettings()
    source = Path(input_path)
    output = Path(output_path)

    _notify(progress, 5, "正在讀取 EPUB…")
    book = parse_epub(
        source,
        content_only=content_only,
        confirmed_back_cover_page=confirmed_back_cover_page,
    )
    warnings = list(book.warnings)
    referenced_images = {
        block.resource_path for block in book.blocks if isinstance(block, ImageBlock)
    }
    image_sizes: dict[str, tuple[int, int]] = {}
    total_images = max(1, len(referenced_images))
    for index, resource_path in enumerate(sorted(referenced_images), start=1):
        data = book.resources.get(resource_path)
        if data is None:
            warnings.append(f"缺少圖片資料：{resource_path}")
            continue
        try:
            image_sizes[resource_path] = _image_size(
                data, book.media_types.get(resource_path, ""), resource_path
            )
        except Exception as exc:
            warnings.append(f"無法測量圖片 {resource_path}：{exc}")
        percent = 10 + int(index / total_images * 20)
        _notify(progress, percent, f"正在分析圖片 {index}/{len(referenced_images)}…")

    page_labels = {
        "signature16": "A6 書帖小頁",
        "four_up": "A6 四格小頁",
        "single_a5": "A5 單頁",
        "single_4x6": "4×6 英吋單頁",
        "b6_on_a5": "B6 內容頁（A5 紙張）",
    }
    _notify(progress, 35, f"正在將內容分成{page_labels[settings.imposition_mode]}…")
    pages = paginate(book.blocks, settings, image_sizes)
    _notify(progress, 65, "正在建立 Word 版面…")
    warnings.extend(
        write_docx(
            pages,
            output,
            resources=book.resources,
            media_types=book.media_types,
            settings=settings,
            title=book.title,
            author=book.author,
            imposition_mode=settings.imposition_mode,
        )
    )
    _notify(progress, 100, "轉換完成。")
    plan = build_imposition(
        len(pages),
        settings.imposition_mode,
        settings.binding_direction,
    )
    return ConversionResult(
        output_path=output,
        title=book.title,
        author=book.author,
        mini_page_count=len(pages),
        a4_page_count=len(plan.sides),
        image_count=len(referenced_images),
        warnings=tuple(dict.fromkeys(warnings)),
        imposition_mode=settings.imposition_mode,
        paper_sheet_count=plan.paper_sheet_count,
        signature_count=plan.signature_count,
        padded_mini_page_count=plan.padded_page_count,
    )


def convert_input(
    input_path: Path | str,
    output_path: Path | str,
    settings: LayoutSettings | None = None,
    progress: ProgressCallback | None = None,
    *,
    content_only: bool = True,
    confirmed_back_cover_page: str | None = None,
) -> ConversionResult:
    """Convert an EPUB or reflow an existing DOCX based on its extension."""
    source = Path(input_path)
    suffix = source.suffix.lower()
    if suffix == ".epub":
        return convert_epub(
            source,
            output_path,
            settings,
            progress,
            content_only=content_only,
            confirmed_back_cover_page=confirmed_back_cover_page,
        )
    if suffix == ".docx":
        from .word_reflow import convert_docx
        return convert_docx(source, output_path, settings, progress)
    raise ValueError("輸入檔案只支援 EPUB 或 DOCX。")
