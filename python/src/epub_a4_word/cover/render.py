from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable

from PIL import (
    Image,
    ImageChops,
    ImageColor,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)

from .fonts import resolve_font
from .geometry import CoverLayout, RectMm, calculate_layout
from .models import CoverElement, CoverProject, ElementKind, ImageMode, Region
from .print_plan import PrintMark, PrintPage


@dataclass(frozen=True)
class RenderResult:
    path: Path
    width_px: int
    height_px: int
    warnings: tuple[str, ...] = ()


class CoverRenderError(ValueError):
    """Raised when a project element cannot be rendered safely."""


def mm_to_px(value_mm: float, dpi: int) -> int:
    if dpi <= 0:
        raise ValueError("DPI 必須大於 0。")
    if not math.isfinite(float(value_mm)):
        raise ValueError("毫米值必須是有限數字。")
    return max(0, round(float(value_mm) / 25.4 * dpi))


def _rect_box(rect: RectMm, dpi: int) -> tuple[int, int, int, int]:
    return (
        mm_to_px(rect.x_mm, dpi),
        mm_to_px(rect.y_mm, dpi),
        mm_to_px(rect.right_mm, dpi),
        mm_to_px(rect.bottom_mm, dpi),
    )


def _rect_size(rect: RectMm, dpi: int) -> tuple[int, int]:
    return (
        max(1, mm_to_px(rect.width_mm, dpi)),
        max(1, mm_to_px(rect.height_mm, dpi)),
    )


def _transform_rect(element: CoverElement) -> RectMm:
    transform = element.transform
    return RectMm(
        float(transform.x_mm),
        float(transform.y_mm),
        float(transform.width_mm),
        float(transform.height_mm),
    )


def _region_rect(layout: CoverLayout, region: Region) -> RectMm:
    return {
        Region.BACK: layout.back_rect,
        Region.SPINE: layout.spine_rect,
        Region.FRONT: layout.front_rect,
        Region.SPREAD: layout.bleed_rect,
    }[region]


def _intersection(first: RectMm, second: RectMm) -> RectMm | None:
    left = max(first.x_mm, second.x_mm)
    top = max(first.y_mm, second.y_mm)
    right = min(first.right_mm, second.right_mm)
    bottom = min(first.bottom_mm, second.bottom_mm)
    if right <= left or bottom <= top:
        return None
    return RectMm(left, top, right - left, bottom - top)


def _parse_color(value: Any, default: str, *, alpha: int = 255) -> tuple[int, int, int, int]:
    try:
        rgb = ImageColor.getrgb(str(value if value is not None else default))
    except (ValueError, TypeError):
        rgb = ImageColor.getrgb(default)
    if len(rgb) == 4:
        return (rgb[0], rgb[1], rgb[2], round(rgb[3] * alpha / 255))
    return (rgb[0], rgb[1], rgb[2], alpha)


def _fit_image(source: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    if fit == "contain":
        result = ImageOps.contain(
            source,
            (width, height),
            Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(
            result.convert("RGBA"),
            ((width - result.width) // 2, (height - result.height) // 2),
        )
        return canvas
    return ImageOps.fit(
        source,
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    ).convert("RGBA")


def _normalized_crop(source: Image.Image, crop: Any) -> Image.Image:
    if crop is None:
        return source
    if isinstance(crop, dict):
        values = (
            crop.get("left", 0.0),
            crop.get("top", 0.0),
            crop.get("right", 1.0),
            crop.get("bottom", 1.0),
        )
    elif isinstance(crop, (list, tuple)) and len(crop) == 4:
        values = tuple(crop)
    else:
        return source
    try:
        left, top, right, bottom = (float(value) for value in values)
    except (TypeError, ValueError):
        return source
    left = min(max(left, 0.0), 1.0)
    top = min(max(top, 0.0), 1.0)
    right = min(max(right, left + 1e-6), 1.0)
    bottom = min(max(bottom, top + 1e-6), 1.0)
    return source.crop(
        (
            round(source.width * left),
            round(source.height * top),
            max(round(source.width * right), round(source.width * left) + 1),
            max(round(source.height * bottom), round(source.height * top) + 1),
        )
    )


def _gradient_overlay(size: tuple[int, int], spec: Any) -> Image.Image | None:
    if not isinstance(spec, dict):
        return None
    start = _parse_color(spec.get("start", "#00000000"), "#00000000")
    end = _parse_color(spec.get("end", "#00000000"), "#00000000")
    direction = str(spec.get("direction", "vertical"))
    width, height = size
    length = width if direction == "horizontal" else height
    if length <= 0:
        return None
    strip = Image.new("RGBA", (length, 1), (0, 0, 0, 0))
    pixels = strip.load()
    for index in range(length):
        ratio = 0.0 if length == 1 else index / (length - 1)
        pixels[index, 0] = tuple(
            round(start[channel] * (1.0 - ratio) + end[channel] * ratio)
            for channel in range(4)
        )
    if direction == "horizontal":
        return strip.resize((width, height))
    return strip.transpose(Image.Transpose.ROTATE_90).resize((width, height))


def _apply_alpha(image: Image.Image, opacity: float) -> Image.Image:
    result = image.convert("RGBA")
    alpha = result.getchannel("A").point(
        lambda value: round(value * min(max(opacity, 0.0), 1.0))
    )
    result.putalpha(alpha)
    return result


def _prepare_image(element: CoverElement, size: tuple[int, int]) -> Image.Image:
    path_value = element.content.get("path")
    if not isinstance(path_value, str) or not Path(path_value).is_file():
        raise CoverRenderError(f"元素 {element.id} 的圖片不存在：{path_value}")
    with Image.open(path_value) as opened:
        source = opened.convert("RGBA")
    source = _normalized_crop(source, element.content.get("crop"))
    if bool(element.content.get("flip_horizontal", False)):
        source = ImageOps.mirror(source)
    if bool(element.content.get("flip_vertical", False)):
        source = ImageOps.flip(source)

    try:
        brightness = float(element.content.get("brightness", 1.0))
    except (TypeError, ValueError):
        brightness = 1.0
    if brightness != 1.0:
        source = ImageEnhance.Brightness(source).enhance(max(0.0, brightness))

    try:
        blur = float(element.content.get("blur", 0.0))
    except (TypeError, ValueError):
        blur = 0.0
    if blur > 0.0:
        source = source.filter(ImageFilter.GaussianBlur(radius=blur))

    local = _fit_image(source, size[0], size[1], str(element.content.get("fit", "cover")))
    rotation = float(element.transform.rotation_deg) + float(
        element.content.get("rotation_deg", 0.0)
    )
    if rotation % 360.0:
        rotated = local.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
        local = ImageOps.fit(
            rotated,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

    try:
        darkness = float(element.content.get("dark_overlay", 0.0))
    except (TypeError, ValueError):
        darkness = 0.0
    if darkness > 0.0:
        overlay = Image.new(
            "RGBA",
            local.size,
            (0, 0, 0, round(255 * min(darkness, 1.0))),
        )
        local = Image.alpha_composite(local, overlay)

    gradient = _gradient_overlay(local.size, element.content.get("gradient"))
    if gradient is not None:
        local = Image.alpha_composite(local, gradient)

    try:
        content_opacity = float(element.content.get("opacity", 1.0))
    except (TypeError, ValueError):
        content_opacity = 1.0
    return _apply_alpha(local, float(element.opacity) * content_opacity)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: Any) -> int:
    if not text:
        return 0
    box = draw.textbbox((0, 0), text, font=font)
    return max(0, box[2] - box[0])


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for character in paragraph:
            candidate = current + character
            if current and _text_width(draw, candidate, font) > max_width:
                lines.append(current.rstrip())
                current = character.lstrip() if character.isspace() else character
            else:
                current = candidate
        lines.append(current.rstrip())
    return lines


def _render_horizontal_text(
    size: tuple[int, int],
    element: CoverElement,
) -> tuple[Image.Image, bool]:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    content = element.content
    try:
        font_size_pt = float(content.get("font_size_pt", 12.0))
    except (TypeError, ValueError):
        font_size_pt = 12.0
    # A 96-DPI point conversion is intentionally not used: the caller's box
    # dimensions are already at export DPI, so use an explicit per-element DPI.
    dpi = int(content.get("_render_dpi", 300))
    size_px = max(1, round(font_size_pt / 72.0 * dpi))
    font = resolve_font(
        str(content.get("font_family", "sans-serif")),
        content.get("font_path") if isinstance(content.get("font_path"), str) else None,
        size_px,
    )
    color = _parse_color(content.get("color", "#111111"), "#111111")
    lines = _wrap_text(draw, str(content.get("text", "")), font, max(1, size[0]))
    sample_box = draw.textbbox((0, 0), "Ag", font=font)
    line_height = max(1, sample_box[3] - sample_box[1])
    try:
        line_spacing = max(0.1, float(content.get("line_spacing", 1.15)))
    except (TypeError, ValueError):
        line_spacing = 1.15
    step = max(1, round(line_height * line_spacing))
    max_lines = max(1, (size[1] + max(0, step - line_height)) // step)
    overflow = len(lines) > max_lines
    visible_lines = lines[:max_lines]
    total_height = line_height + max(0, len(visible_lines) - 1) * step
    vertical_align = str(content.get("vertical_align", "top"))
    if vertical_align == "center":
        y = max(0, (size[1] - total_height) // 2)
    elif vertical_align == "bottom":
        y = max(0, size[1] - total_height)
    else:
        y = 0
    align = str(content.get("align", "center"))
    for line in visible_lines:
        width = _text_width(draw, line, font)
        if align == "left":
            x = 0
        elif align == "right":
            x = max(0, size[0] - width)
        else:
            x = max(0, (size[0] - width) // 2)
        draw.text((x, y), line, font=font, fill=color)
        y += step
    return canvas, overflow


def _prepare_text(
    element: CoverElement,
    size: tuple[int, int],
    dpi: int,
) -> tuple[Image.Image, bool]:
    content = dict(element.content)
    content["_render_dpi"] = dpi
    local_element = CoverElement(
        id=element.id,
        kind=element.kind,
        region=element.region,
        transform=element.transform,
        z_index=element.z_index,
        opacity=element.opacity,
        content=content,
    )
    rotation = float(element.transform.rotation_deg)
    normalized = rotation % 360.0
    if math.isclose(normalized, 90.0, abs_tol=1e-9) or math.isclose(
        normalized, 270.0, abs_tol=1e-9
    ):
        pre_size = (size[1], size[0])
        horizontal, overflow = _render_horizontal_text(pre_size, local_element)
        local = horizontal.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
        local = ImageOps.fit(local, size, method=Image.Resampling.LANCZOS)
    else:
        horizontal, overflow = _render_horizontal_text(size, local_element)
        if normalized:
            rotated = horizontal.rotate(
                -rotation,
                expand=True,
                resample=Image.Resampling.BICUBIC,
            )
            local = ImageOps.fit(rotated, size, method=Image.Resampling.LANCZOS)
        else:
            local = horizontal
    return _apply_alpha(local, float(element.opacity)), overflow


def _prepare_shape(element: CoverElement, size: tuple[int, int], dpi: int) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    fill = _parse_color(element.content.get("fill", "#00000000"), "#00000000")
    stroke_value = element.content.get("stroke")
    stroke = None if stroke_value in (None, "", "none") else _parse_color(stroke_value, "#111111")
    try:
        stroke_width = max(1, round(float(element.content.get("stroke_width", 0.3)) / 25.4 * dpi))
    except (TypeError, ValueError):
        stroke_width = 1
    bounds = (0, 0, max(0, size[0] - 1), max(0, size[1] - 1))
    if str(element.content.get("shape", "rectangle")) == "ellipse":
        draw.ellipse(bounds, fill=fill, outline=stroke, width=stroke_width)
    else:
        draw.rectangle(bounds, fill=fill, outline=stroke, width=stroke_width)
    return _apply_alpha(canvas, float(element.opacity))


def _prepare_barcode(element: CoverElement, size: tuple[int, int], dpi: int) -> Image.Image:
    canvas = Image.new("RGBA", size, (255, 255, 255, round(255 * element.opacity)))
    draw = ImageDraw.Draw(canvas)
    border = max(1, mm_to_px(0.2, dpi))
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="black", width=border)
    bar_area_height = max(1, round(size[1] * 0.62))
    x = max(2, round(size[0] * 0.08))
    limit = max(x + 1, round(size[0] * 0.92))
    widths = (1, 2, 1, 3, 1, 1, 2, 2, 1, 3)
    index = 0
    while x < limit:
        width = max(1, widths[index % len(widths)] * max(1, size[0] // 120))
        draw.rectangle((x, 2, min(limit, x + width), bar_area_height), fill="black")
        x += width * 2
        index += 1
    text = str(element.content.get("text", "ISBN"))
    font = resolve_font("sans-serif", None, max(8, round(size[1] * 0.18)))
    draw.text((max(2, round(size[0] * 0.05)), bar_area_height + 2), text, fill="black", font=font)
    return canvas


def _clip_layer(
    layer: Image.Image,
    clip_rect: RectMm | None,
    dpi: int,
) -> Image.Image:
    if clip_rect is None:
        return Image.new("RGBA", layer.size, (0, 0, 0, 0))
    mask = Image.new("L", layer.size, 0)
    draw = ImageDraw.Draw(mask)
    left, top, right, bottom = _rect_box(clip_rect, dpi)
    draw.rectangle((left, top, max(left, right - 1), max(top, bottom - 1)), fill=255)
    alpha = ImageChops.multiply(layer.getchannel("A"), mask)
    result = layer.copy()
    result.putalpha(alpha)
    return result


def _element_clip(project: CoverProject, layout: CoverLayout, element: CoverElement) -> RectMm | None:
    element_rect = _transform_rect(element)
    if element.kind is ElementKind.IMAGE:
        if project.image_mode is ImageMode.FRONT_ONLY:
            mode_rect = layout.front_rect
        elif project.image_mode is ImageMode.SEPARATE_COVERS:
            mode_rect = _region_rect(layout, element.region)
        else:
            mode_rect = layout.bleed_rect
        return _intersection(element_rect, mode_rect)
    return _intersection(element_rect, _region_rect(layout, element.region))


def _render_spread_with_warnings(
    project: CoverProject,
    dpi: int,
) -> tuple[Image.Image, tuple[str, ...]]:
    layout = calculate_layout(project)
    canvas_size = _rect_size(layout.bleed_rect, dpi)
    background = _parse_color(project.background.get("color", "#ffffff"), "#ffffff")
    canvas = Image.new("RGBA", canvas_size, background)
    warnings: list[str] = []

    ordered: Iterable[tuple[int, CoverElement]] = sorted(
        enumerate(project.elements),
        key=lambda item: (item[1].z_index, item[0]),
    )
    for _, element in ordered:
        if element.kind is ElementKind.GUIDE and not bool(
            element.content.get("printable", False)
        ):
            continue
        rect = _transform_rect(element)
        width, height = _rect_size(rect, dpi)
        if element.kind is ElementKind.IMAGE:
            local = _prepare_image(element, (width, height))
        elif element.kind is ElementKind.TEXT:
            local, overflow = _prepare_text(element, (width, height), dpi)
            if overflow:
                warnings.append(f"元素 {element.id} 文字溢出。")
        elif element.kind is ElementKind.BARCODE_PLACEHOLDER:
            local = _prepare_barcode(element, (width, height), dpi)
        else:
            local = _prepare_shape(element, (width, height), dpi)

        layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        layer.alpha_composite(
            local,
            (mm_to_px(rect.x_mm, dpi), mm_to_px(rect.y_mm, dpi)),
        )
        layer = _clip_layer(layer, _element_clip(project, layout, element), dpi)
        canvas = Image.alpha_composite(canvas, layer)

    return canvas, tuple(dict.fromkeys(warnings))


def render_spread(project: CoverProject, dpi: int) -> Image.Image:
    image, _ = _render_spread_with_warnings(project, dpi)
    return image


def render_preview(
    project: CoverProject,
    output_path: Path | str,
    max_px: int = 1600,
) -> RenderResult:
    if max_px < 1:
        raise ValueError("max_px 必須大於 0。")
    image, warnings = _render_spread_with_warnings(project, dpi=96)
    if image.width >= image.height:
        target_size = (
            max_px,
            max(1, round(image.height * max_px / image.width)),
        )
    else:
        target_size = (
            max(1, round(image.width * max_px / image.height)),
            max_px,
        )
    if image.size != target_size:
        image = image.resize(target_size, Image.Resampling.LANCZOS)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return RenderResult(output, image.width, image.height, warnings)


def _draw_print_mark(draw: ImageDraw.ImageDraw, mark: PrintMark, dpi: int) -> None:
    x1 = mm_to_px(mark.x1_mm, dpi)
    y1 = mm_to_px(mark.y1_mm, dpi)
    if mark.kind == "label":
        font = resolve_font("sans-serif", None, max(8, round(dpi / 12)))
        box = draw.textbbox((0, 0), mark.label, font=font)
        width = box[2] - box[0]
        draw.text((x1 - width // 2, y1), mark.label, fill="black", font=font)
        return
    if mark.x2_mm is None or mark.y2_mm is None:
        return
    draw.line(
        (
            x1,
            y1,
            mm_to_px(mark.x2_mm, dpi),
            mm_to_px(mark.y2_mm, dpi),
        ),
        fill="black",
        width=max(1, round(dpi / 300)),
    )


def render_print_page(
    project: CoverProject,
    page: PrintPage,
    dpi: int,
) -> Image.Image:
    spread = render_spread(project, dpi)
    page_width_mm, page_height_mm = page.paper_size_mm
    canvas = Image.new(
        "RGB",
        (mm_to_px(page_width_mm, dpi), mm_to_px(page_height_mm, dpi)),
        "white",
    )
    source_box = _rect_box(page.source_rect, dpi)
    crop = spread.crop(source_box).convert("RGB")
    destination = (
        mm_to_px(page.destination_rect.x_mm, dpi),
        mm_to_px(page.destination_rect.y_mm, dpi),
    )
    # Source and destination use the same DPI and scale=1.0: paste directly.
    canvas.paste(crop, destination)
    draw = ImageDraw.Draw(canvas)
    for mark in page.marks:
        _draw_print_mark(draw, mark, dpi)
    return canvas
