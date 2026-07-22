from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Iterable, Literal, Mapping

from .imposition import ImpositionMode
from .models import ContentBlock, ImageBlock, PageBreakBlock, TextBlock, TextRun


MarginMode = Literal["safe", "maximized", "borderless"]
PT_PER_CM = 72.0 / 2.54
A4_WIDTH_CM = 21.0
A4_HEIGHT_CM = 29.7
A5_WIDTH_CM = 14.8
A5_HEIGHT_CM = 21.0
PHOTO_4X6_WIDTH_CM = 10.16
PHOTO_4X6_HEIGHT_CM = 15.24
A4_PAGE_PREFIX_HEIGHT_CM = 0.50
SINGLE_PAGE_PREFIX_HEIGHT_CM = 0.30


@dataclass(frozen=True)
class _MarginPreset:
    outer_margin_cm: float
    cell_outer_margin_cm: float
    gutter_margin_cm: float
    cell_vertical_margin_cm: float


_MARGIN_PRESETS: dict[MarginMode, _MarginPreset] = {
    "safe": _MarginPreset(
        outer_margin_cm=0.5,
        cell_outer_margin_cm=0.35,
        gutter_margin_cm=0.50,
        cell_vertical_margin_cm=0.30,
    ),
    "maximized": _MarginPreset(
        outer_margin_cm=0.2,
        cell_outer_margin_cm=0.18,
        gutter_margin_cm=0.42,
        cell_vertical_margin_cm=0.18,
    ),
    "borderless": _MarginPreset(
        outer_margin_cm=0.0,
        cell_outer_margin_cm=0.08,
        gutter_margin_cm=0.35,
        cell_vertical_margin_cm=0.08,
    ),
}


@dataclass(frozen=True)
class LayoutSettings:
    imposition_mode: ImpositionMode = "signature16"
    margin_mode: MarginMode = "maximized"
    font_name: str = "Noto Serif CJK TC"
    body_font_pt: float = 8.5
    heading_font_pt: float = 11.0
    line_spacing: float = 1.23
    paragraph_spacing_pt: float = 2.5
    heading_spacing_pt: float = 5.0
    content_width_pt: float | None = None
    content_height_pt: float | None = None
    max_image_width_pt: float | None = None
    max_image_height_pt: float | None = None
    page_numbers: bool = True
    cut_guides: bool = True
    first_line_indent_chars: float = 2.0
    outer_margin_cm: float | None = None
    cell_width_cm: float | None = None
    cell_height_cm: float | None = None
    cell_outer_margin_cm: float | None = None
    gutter_margin_cm: float | None = None
    cell_vertical_margin_cm: float | None = None
    page_number_footer_pt: float = 12.0
    pagination_safety_pt: float = 18.0
    paper_width_cm: float | None = None
    paper_height_cm: float | None = None
    grid_rows: int | None = None
    grid_cols: int | None = None
    page_prefix_height_cm: float | None = None


@dataclass
class MiniPage:
    blocks: list[TextBlock | ImageBlock] = field(default_factory=list)
    used_points: float = 0.0
    logical_page_number: int | None = None

    @property
    def has_text(self) -> bool:
        return any(isinstance(block, TextBlock) and bool(block.text.strip()) for block in self.blocks)


def resolve_layout(settings: LayoutSettings) -> LayoutSettings:
    """Resolve paper, grid, margins, and content dimensions for one output mode.

    Explicit dimensions supplied by tests or advanced callers are preserved.
    """

    try:
        preset = _MARGIN_PRESETS[settings.margin_mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported margin mode: {settings.margin_mode}") from exc

    if settings.imposition_mode in {"four_up", "signature16"}:
        default_paper_width = A4_WIDTH_CM
        default_paper_height = A4_HEIGHT_CM
        default_rows = 2
        default_cols = 2
        default_prefix = A4_PAGE_PREFIX_HEIGHT_CM
    elif settings.imposition_mode == "single_a5":
        default_paper_width = A5_WIDTH_CM
        default_paper_height = A5_HEIGHT_CM
        default_rows = 1
        default_cols = 1
        default_prefix = SINGLE_PAGE_PREFIX_HEIGHT_CM
    elif settings.imposition_mode == "single_4x6":
        default_paper_width = PHOTO_4X6_WIDTH_CM
        default_paper_height = PHOTO_4X6_HEIGHT_CM
        default_rows = 1
        default_cols = 1
        default_prefix = SINGLE_PAGE_PREFIX_HEIGHT_CM
    else:
        raise ValueError(f"Unsupported imposition mode: {settings.imposition_mode}")

    paper_width = default_paper_width if settings.paper_width_cm is None else settings.paper_width_cm
    paper_height = default_paper_height if settings.paper_height_cm is None else settings.paper_height_cm
    grid_rows = default_rows if settings.grid_rows is None else settings.grid_rows
    grid_cols = default_cols if settings.grid_cols is None else settings.grid_cols
    prefix_height = (
        default_prefix if settings.page_prefix_height_cm is None else settings.page_prefix_height_cm
    )
    if grid_rows < 1 or grid_cols < 1:
        raise ValueError("grid_rows and grid_cols must be positive")

    outer = preset.outer_margin_cm if settings.outer_margin_cm is None else settings.outer_margin_cm
    cell_width = (
        (paper_width - 2 * outer) / grid_cols
        if settings.cell_width_cm is None
        else settings.cell_width_cm
    )
    cell_height = (
        (paper_height - 2 * outer - prefix_height) / grid_rows
        if settings.cell_height_cm is None
        else settings.cell_height_cm
    )
    cell_outer = (
        preset.cell_outer_margin_cm
        if settings.cell_outer_margin_cm is None
        else settings.cell_outer_margin_cm
    )
    gutter = preset.gutter_margin_cm if settings.gutter_margin_cm is None else settings.gutter_margin_cm
    vertical = (
        preset.cell_vertical_margin_cm
        if settings.cell_vertical_margin_cm is None
        else settings.cell_vertical_margin_cm
    )

    footer = settings.page_number_footer_pt if settings.page_numbers else 0.0
    horizontal_cell_margins = 2 * cell_outer if grid_cols == 1 else cell_outer + gutter
    content_width = (
        max(40.0, (cell_width - horizontal_cell_margins) * PT_PER_CM)
        if settings.content_width_pt is None
        else settings.content_width_pt
    )
    content_height = (
        max(
            60.0,
            (cell_height - 2 * vertical) * PT_PER_CM
            - footer
            - settings.pagination_safety_pt,
        )
        if settings.content_height_pt is None
        else settings.content_height_pt
    )
    max_image_width = content_width if settings.max_image_width_pt is None else settings.max_image_width_pt
    max_image_height = content_height if settings.max_image_height_pt is None else settings.max_image_height_pt

    return replace(
        settings,
        paper_width_cm=paper_width,
        paper_height_cm=paper_height,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        page_prefix_height_cm=prefix_height,
        outer_margin_cm=outer,
        cell_width_cm=cell_width,
        cell_height_cm=cell_height,
        cell_outer_margin_cm=cell_outer,
        gutter_margin_cm=gutter,
        cell_vertical_margin_cm=vertical,
        content_width_pt=content_width,
        content_height_pt=content_height,
        max_image_width_pt=max_image_width,
        max_image_height_pt=max_image_height,
    )


def _char_weight(char: str) -> float:
    if char == "\n":
        return 0.0
    if char.isspace():
        return 0.35
    if unicodedata.east_asian_width(char) in {"W", "F", "A"}:
        return 1.0
    return 0.55


def _font_for(block: TextBlock, settings: LayoutSettings) -> float:
    return settings.heading_font_pt if block.style == "heading" else settings.body_font_pt


def _chars_per_line(block: TextBlock, settings: LayoutSettings) -> float:
    assert settings.content_width_pt is not None
    font_pt = _font_for(block, settings)
    return max(4.0, settings.content_width_pt / (font_pt * 1.07))


def measure_text(block: TextBlock, settings: LayoutSettings) -> float:
    settings = resolve_layout(settings)
    font_pt = _font_for(block, settings)
    per_line = _chars_per_line(block, settings)
    lines = 0
    for logical_line in block.text.split("\n"):
        weight = sum(_char_weight(char) for char in logical_line)
        if block.style == "body" and logical_line:
            weight += settings.first_line_indent_chars
        lines += max(1, math.ceil(weight / per_line))
    spacing = settings.heading_spacing_pt if block.style == "heading" else settings.paragraph_spacing_pt
    return lines * font_pt * settings.line_spacing + spacing


def measure_image(
    block: ImageBlock,
    settings: LayoutSettings,
    image_sizes: Mapping[str, tuple[int, int]],
) -> float:
    settings = resolve_layout(settings)
    assert settings.max_image_width_pt is not None
    assert settings.max_image_height_pt is not None
    assert settings.content_height_pt is not None
    width_px, height_px = image_sizes.get(block.resource_path, (1, 1))
    if width_px <= 0 or height_px <= 0:
        width_px, height_px = (1, 1)
    rendered_width = settings.max_image_width_pt
    rendered_height = rendered_width * height_px / width_px
    if rendered_height > settings.max_image_height_pt:
        rendered_height = settings.max_image_height_pt
    return min(settings.content_height_pt, rendered_height + settings.paragraph_spacing_pt)


def _split_runs_at(runs: tuple[TextRun, ...], char_index: int) -> tuple[tuple[TextRun, ...], tuple[TextRun, ...]]:
    left: list[TextRun] = []
    right: list[TextRun] = []
    consumed = 0
    for run in runs:
        next_consumed = consumed + len(run.text)
        if next_consumed <= char_index:
            left.append(run)
        elif consumed >= char_index:
            right.append(run)
        else:
            offset = char_index - consumed
            if offset > 0:
                left.append(TextRun(run.text[:offset], run.bold, run.italic))
            if offset < len(run.text):
                right.append(TextRun(run.text[offset:], run.bold, run.italic))
        consumed = next_consumed
    return tuple(left), tuple(right)


def _find_split_index(block: TextBlock, available_points: float, settings: LayoutSettings) -> int:
    font_pt = _font_for(block, settings)
    spacing = settings.heading_spacing_pt if block.style == "heading" else settings.paragraph_spacing_pt
    usable = max(0.0, available_points - spacing)
    max_lines = max(1, int(usable // (font_pt * settings.line_spacing)))
    target_weight = max_lines * _chars_per_line(block, settings)
    if block.style == "body":
        target_weight = max(1.0, target_weight - settings.first_line_indent_chars)

    weight = 0.0
    best_break = 0
    preferred_break = 0
    preferred_chars = set("。！？；：.!?;:\n")
    for index, char in enumerate(block.text, start=1):
        weight += _char_weight(char)
        if char in preferred_chars:
            preferred_break = index
        if weight > target_weight:
            break
        best_break = index
    if best_break >= len(block.text):
        return len(block.text)
    if preferred_break >= max(1, int(best_break * 0.65)):
        return preferred_break
    return max(1, best_break)


def split_text_block(
    block: TextBlock,
    available_points: float,
    settings: LayoutSettings,
) -> tuple[TextBlock, TextBlock | None]:
    settings = resolve_layout(settings)
    split_at = _find_split_index(block, available_points, settings)
    if split_at >= len(block.text):
        return block, None
    left_runs, right_runs = _split_runs_at(block.runs, split_at)
    left = TextBlock(left_runs, style=block.style, page_break_before=block.page_break_before)
    right = TextBlock(right_runs, style=block.style, page_break_before=False)
    return left, right


_PROLOGUE_RE = re.compile(r"^\s*(?:序\s*章|序章|楔子|prologue\b)", re.IGNORECASE)
_CHAPTER_RE = re.compile(
    r"^\s*第\s*[0-9０-９一二三四五六七八九十百兩两]+\s*[章回節节]",
    re.IGNORECASE,
)


def _numbering_start_index(pages: list[MiniPage]) -> int | None:
    for index, page in enumerate(pages):
        for block in page.blocks:
            if isinstance(block, TextBlock) and block.style == "heading" and _PROLOGUE_RE.search(block.text):
                return index
    for index, page in enumerate(pages):
        for block in page.blocks:
            if isinstance(block, TextBlock) and block.style == "heading" and _CHAPTER_RE.search(block.text):
                return index
    for index, page in enumerate(pages):
        if page.has_text:
            return index
    return None


def _assign_logical_page_numbers(pages: list[MiniPage]) -> None:
    start = _numbering_start_index(pages)
    if start is None:
        return
    for logical_number, page in enumerate(pages[start:], start=1):
        page.logical_page_number = logical_number


def paginate(
    blocks: Iterable[ContentBlock],
    settings: LayoutSettings,
    image_sizes: Mapping[str, tuple[int, int]],
) -> list[MiniPage]:
    settings = resolve_layout(settings)
    assert settings.content_height_pt is not None
    pages: list[MiniPage] = []
    current = MiniPage()

    def flush() -> None:
        nonlocal current
        if current.blocks:
            pages.append(current)
        current = MiniPage()

    queue: list[ContentBlock] = list(blocks)
    while queue:
        block = queue.pop(0)
        if isinstance(block, PageBreakBlock):
            flush()
            continue
        if getattr(block, "page_break_before", False) and current.blocks:
            flush()

        if isinstance(block, ImageBlock):
            height = measure_image(block, settings, image_sizes)
            if current.blocks and current.used_points + height > settings.content_height_pt:
                flush()
            current.blocks.append(block)
            current.used_points += height
            if current.used_points >= settings.content_height_pt - 0.01:
                flush()
            continue

        height = measure_text(block, settings)
        remaining = settings.content_height_pt - current.used_points
        if height <= remaining + 0.01:
            current.blocks.append(block)
            current.used_points += height
            continue

        if current.blocks and remaining < _font_for(block, settings) * settings.line_spacing * 2:
            flush()
            queue.insert(0, block)
            continue

        first, remainder = split_text_block(
            block,
            max(remaining, settings.content_height_pt if not current.blocks else remaining),
            settings,
        )
        first_height = measure_text(first, settings)
        while (
            first_height > max(remaining, settings.content_height_pt if not current.blocks else remaining) + 0.01
            and len(first.text) > 1
        ):
            left_runs, right_runs = _split_runs_at(first.runs, len(first.text) - 1)
            moved = right_runs + (remainder.runs if remainder else ())
            first = TextBlock(left_runs, style=block.style, page_break_before=block.page_break_before)
            remainder = TextBlock(moved, style=block.style)
            first_height = measure_text(first, settings)
        current.blocks.append(first)
        current.used_points += min(first_height, settings.content_height_pt)
        flush()
        if remainder and remainder.text:
            queue.insert(0, remainder)

    flush()
    _assign_logical_page_numbers(pages)
    return pages
