from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

from PIL import Image

from .geometry import RectMm, calculate_layout
from .models import CoverProject
from .search.models import CandidateCategory


@dataclass(frozen=True)
class CompositionSelection:
    path: Path
    category: CandidateCategory
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float = 0.0
    crop_bottom: float = 0.0
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "category", CandidateCategory(self.category))
        for name in ("crop_left", "crop_top", "crop_right", "crop_bottom"):
            value = float(getattr(self, name))
            if not 0.0 <= value < 1.0:
                raise ValueError(f"{name} 必須介於 0 與 1。")
        if self.crop_left + self.crop_right >= 1.0:
            raise ValueError("水平裁切範圍無效。")
        if self.crop_top + self.crop_bottom >= 1.0:
            raise ValueError("垂直裁切範圍無效。")
        if self.scale <= 0:
            raise ValueError("scale 必須大於 0。")


def _mm_to_px(value: float, dpi: int) -> int:
    return max(1, round(value / 25.4 * dpi))


def _rect_to_px(rect: RectMm, origin: RectMm, dpi: int) -> tuple[int, int, int, int]:
    left = _mm_to_px(rect.x_mm - origin.x_mm, dpi)
    top = _mm_to_px(rect.y_mm - origin.y_mm, dpi)
    width = _mm_to_px(rect.width_mm, dpi)
    height = _mm_to_px(rect.height_mm, dpi)
    return left, top, width, height


def _render_selection(selection: CompositionSelection, target_size: tuple[int, int]) -> Image.Image:
    with Image.open(selection.path) as source:
        image = source.convert("RGBA")
    width, height = image.size
    left = round(width * selection.crop_left)
    top = round(height * selection.crop_top)
    right = round(width * (1.0 - selection.crop_right))
    bottom = round(height * (1.0 - selection.crop_bottom))
    image = image.crop((left, top, max(left + 1, right), max(top + 1, bottom)))

    target_width, target_height = target_size
    cover_scale = max(target_width / image.width, target_height / image.height)
    final_scale = cover_scale * selection.scale
    rendered = image.resize(
        (
            max(1, round(image.width * final_scale)),
            max(1, round(image.height * final_scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    layer = Image.new("RGBA", target_size, (0, 0, 0, 0))
    x = round((target_width - rendered.width) / 2 + selection.offset_x * target_width)
    y = round((target_height - rendered.height) / 2 + selection.offset_y * target_height)
    layer.alpha_composite(rendered, (x, y))
    return layer


def compose_full_spread(
    project: CoverProject,
    selections: Mapping[CandidateCategory | str, CompositionSelection],
    output_path: Path | str,
    dpi: int = 300,
) -> Path:
    if dpi < 72 or dpi > 1200:
        raise ValueError("dpi 必須介於 72 與 1200。")
    layout = calculate_layout(project)
    canvas = Image.new(
        "RGBA",
        (
            _mm_to_px(layout.bleed_rect.width_mm, dpi),
            _mm_to_px(layout.bleed_rect.height_mm, dpi),
        ),
        (0, 0, 0, 0),
    )
    targets = {
        CandidateCategory.BACK: layout.back_rect,
        CandidateCategory.SPINE: layout.spine_rect,
        CandidateCategory.FRONT: layout.front_rect,
        CandidateCategory.FULL_SPREAD: layout.bleed_rect,
    }

    normalized = {CandidateCategory(key): value for key, value in selections.items()}
    if CandidateCategory.FULL_SPREAD in normalized:
        selection = normalized[CandidateCategory.FULL_SPREAD]
        layer = _render_selection(selection, canvas.size)
        canvas.alpha_composite(layer)
    else:
        for category in (
            CandidateCategory.BACK,
            CandidateCategory.SPINE,
            CandidateCategory.FRONT,
        ):
            selection = normalized.get(category)
            if selection is None:
                continue
            left, top, width, height = _rect_to_px(
                targets[category], layout.bleed_rect, dpi
            )
            layer = _render_selection(selection, (width, height))
            canvas.alpha_composite(layer, (left, top))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    canvas.save(temporary, format="PNG")
    os.replace(temporary, output)
    return output.resolve()
