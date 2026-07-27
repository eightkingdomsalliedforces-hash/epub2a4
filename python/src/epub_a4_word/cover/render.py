from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
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

from .barcode_layout import BarcodeTextAnchor, build_barcode_layout
from .fonts import resolve_font
from .isbn import normalize_isbn
from .geometry import CoverLayout, RectMm, calculate_layout
from .models import CoverElement, CoverProject, ElementKind, ImageMode, Region
from .print_plan import PrintMark, PrintPage
from .typography import font_candidates
from .search.logo_download import _validate_svg


@dataclass(frozen=True)
class RenderResult:
    path: Path
    width_px: int
    height_px: int
    warnings: tuple[str, ...] = ()


class CoverRenderError(ValueError):
    """Raised when a project element cannot be rendered safely."""


class SvgRendererUnavailableError(CoverRenderError):
    """Raised when a safe SVG has no available rasterizer on this platform."""


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


def transform_image_to_box(
    source: Image.Image,
    size: tuple[int, int],
    *,
    fit: str = "cover",
    scale: float = 1.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    crop: Any = None,
) -> Image.Image:
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    cropped = _normalized_crop(source.convert("RGBA"), crop)
    source_width, source_height = cropped.size
    if source_width < 1 or source_height < 1:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mode = str(fit).casefold()
    if mode not in {"contain", "cover", "original"}:
        mode = "cover"
    contain_ratio = min(width / source_width, height / source_height)
    base_ratio = (
        max(width / source_width, height / source_height)
        if mode == "cover"
        else contain_ratio
    )
    try:
        content_scale = min(5.0, max(0.1, float(scale)))
    except (TypeError, ValueError):
        content_scale = 1.0
    try:
        normalized_x = min(1.0, max(-1.0, float(offset_x)))
        normalized_y = min(1.0, max(-1.0, float(offset_y)))
    except (TypeError, ValueError):
        normalized_x = normalized_y = 0.0
    ratio = max(1e-9, base_ratio * content_scale)
    resized = cropped.resize(
        (max(1, round(source_width * ratio)), max(1, round(source_height * ratio))),
        Image.Resampling.LANCZOS,
    )
    x = round((width - resized.width) / 2.0 + normalized_x * width)
    y = round((height - resized.height) / 2.0 + normalized_y * height)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(resized, (x, y), resized)
    return canvas


def _fit_image(source: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    return transform_image_to_box(source, (width, height), fit=fit)


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
    source_path = Path(path_value)
    if source_path.suffix.casefold() == ".svg":
        data = source_path.read_bytes()
        _validate_svg(data)
        try:
            import cairosvg
        except ImportError as exc:
            raise SvgRendererUnavailableError(
                "目前平台缺少 SVG 轉換元件，已略過出版社 Logo。"
            ) from exc
        try:
            png = cairosvg.svg2png(bytestring=data, unsafe=False)
            with Image.open(BytesIO(png)) as opened:
                source = opened.convert("RGBA")
        except Exception as exc:
            raise CoverRenderError(f"無法轉換 SVG Logo：{source_path}") from exc
    else:
        with Image.open(source_path) as opened:
            source = opened.convert("RGBA")
    crop = element.content.get("crop")
    if crop is None and any(
        key in element.content
        for key in ("crop_left", "crop_top", "crop_right", "crop_bottom")
    ):
        crop = {
            "left": float(element.content.get("crop_left", 0.0)),
            "top": float(element.content.get("crop_top", 0.0)),
            "right": 1.0 - float(element.content.get("crop_right", 0.0)),
            "bottom": 1.0 - float(element.content.get("crop_bottom", 0.0)),
        }
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

    local = transform_image_to_box(
        source,
        size,
        fit=str(element.content.get("fit", "cover")),
        scale=element.content.get("scale", 1.0),
        offset_x=element.content.get("offset_x", element.content.get("crop_x", 0.0)),
        offset_y=element.content.get("offset_y", element.content.get("crop_y", 0.0)),
        crop=crop,
    )
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
    families = font_candidates(
        str(content.get("font_role", "default")),
        content.get("font_families", content.get("font_family", "sans-serif")),
    )
    font = resolve_font(
        families[0],
        content.get("font_path") if isinstance(content.get("font_path"), str) else None,
        size_px,
        families[1:],
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
    del dpi
    isbn = normalize_isbn(element.content.get("isbn", element.content.get("text", "")))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    if len(isbn) != 13:
        return canvas
    layout = build_barcode_layout(isbn, element.content.get("addon", ""))
    draw = ImageDraw.Draw(canvas)
    width, height = size
    for bar in layout.bars:
        left = round(bar.x * width)
        top = round(bar.top * height)
        right = max(left + 1, round((bar.x + bar.width) * width))
        bottom = max(top + 1, round(bar.bottom * height))
        draw.rectangle((left, top, right - 1, bottom - 1), fill="black")

    families = font_candidates(
        "ocr",
        element.content.get("font_families", element.content.get("font_family", "OCR-B")),
    )
    font = resolve_font(
        families[0],
        element.content.get("font_path")
        if isinstance(element.content.get("font_path"), str)
        else None,
        max(8, round(height * 0.13)),
        families[1:],
    )

    def draw_anchor(anchor: BarcodeTextAnchor) -> None:
        left = round(anchor.left * width)
        top = round(anchor.top * height)
        right = max(left + 1, round(anchor.right * width))
        bottom = max(top + 1, round(anchor.bottom * height))
        box = draw.textbbox((0, 0), anchor.text, font=font)
        text_width = max(0, box[2] - box[0])
        text_height = max(0, box[3] - box[1])
        if anchor.align == "left":
            x = left
        elif anchor.align == "right":
            x = max(left, right - text_width)
        else:
            x = left + max(0, (right - left - text_width) // 2)
        y = top + max(0, (bottom - top - text_height) // 2) - box[1]
        draw.text((x, y), anchor.text, fill="black", font=font)

    draw_anchor(layout.first_digit)
    draw_anchor(layout.left_digits)
    draw_anchor(layout.right_digits)
    if layout.addon_digits is not None:
        draw_anchor(layout.addon_digits)
    return _apply_alpha(canvas, float(element.opacity))

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
            try:
                local = _prepare_image(element, (width, height))
            except SvgRendererUnavailableError as exc:
                warnings.append(str(exc))
                continue
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


def _draw_segmented_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    style: str,
    width: int,
    dpi: int,
) -> None:
    if style == "solid":
        draw.line((*start, *end), fill="black", width=width)
        return
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        return
    if style == "dotted":
        on_px = max(1, mm_to_px(0.7, dpi))
        off_px = max(1, mm_to_px(1.3, dpi))
    else:
        on_px = max(1, mm_to_px(3.0, dpi))
        off_px = max(1, mm_to_px(1.8, dpi))
    cursor = 0.0
    while cursor < length:
        segment_end = min(length, cursor + on_px)
        ratio_start = cursor / length
        ratio_end = segment_end / length
        draw.line(
            (
                round(start[0] + dx * ratio_start),
                round(start[1] + dy * ratio_start),
                round(start[0] + dx * ratio_end),
                round(start[1] + dy * ratio_end),
            ),
            fill="black",
            width=width,
        )
        cursor += on_px + off_px


def _draw_print_mark(draw: ImageDraw.ImageDraw, mark: PrintMark, dpi: int) -> None:
    x1 = mm_to_px(mark.x1_mm, dpi)
    y1 = mm_to_px(mark.y1_mm, dpi)
    if mark.kind == "label":
        if mark.role == "label":
            size = max(9, round(dpi / 9))
        else:
            size = max(8, round(dpi / 12))
        font = resolve_font("sans-serif", None, size)
        box = draw.textbbox((0, 0), mark.label, font=font)
        width = box[2] - box[0]
        draw.text((x1 - width // 2, y1), mark.label, fill="black", font=font)
        return
    if mark.x2_mm is None or mark.y2_mm is None:
        return
    _draw_segmented_line(
        draw,
        (x1, y1),
        (mm_to_px(mark.x2_mm, dpi), mm_to_px(mark.y2_mm, dpi)),
        style=mark.line_style,
        width=max(1, round(dpi / 300)),
        dpi=dpi,
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
