from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .geometry import CoverLayout, RectMm, calculate_layout
from .isbn import normalize_ean_addon, normalize_isbn
from .publisher_info_layout import layout_publisher_info
from .spine_layout import build_spine_slots
from .models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
)


@dataclass(frozen=True)
class TemplateSummary:
    id: str
    name: str
    description: str


_TEMPLATE_CATALOG: tuple[TemplateSummary, ...] = (
    TemplateSummary("minimal_text", "極簡文字", "以書名、作者與出版資訊為主。"),
    TemplateSummary(
        "front_image_plain_back",
        "封面圖片／純色封底",
        "保留封面圖片區，封底使用簡潔文字配置。",
    ),
    TemplateSummary(
        "full_spread",
        "全展開圖片",
        "圖片可橫跨封底、書脊與封面。",
    ),
    TemplateSummary(
        "top_bottom_blocks",
        "上下色塊",
        "以可編輯色塊分隔標題與出版資訊。",
    ),
    TemplateSummary(
        "publisher_back_matter_with_spine",
        "出版社封底＋直式書脊",
        "出版社式 ISBN／條碼封底與依書脊寬度自動調整的直式書脊。",
    ),
)

STANDARD_TEMPLATE_IDS = frozenset(
    {
        "front-title",
        "front-author",
        "spine-title",
        "spine-author",
        "spine-background",
        "spine-publisher-logo",
        "spine-title-main",
        "spine-title-english",
        "spine-volume",
        "spine-arc",
        "spine-internal-code",
        "spine-publisher-name",
        "back-description",
        "back-publisher",
        "back-isbn",
        "back-isbn-label",
        "back-isbn-code",
        "back-publisher-info",
        "back-publisher-heading",
        "back-publisher-details",
    }
)


def list_templates() -> tuple[TemplateSummary, ...]:
    return _TEMPLATE_CATALOG


def text_element(
    element_id: str,
    region: Region,
    rect: RectMm,
    text: str,
    font_size_pt: float,
    align: str = "center",
    rotation_deg: float = 0.0,
    *,
    font_weight: int = 400,
    color: str = "#111111",
    z_index: int = 10,
    font_role: str = "default",
    font_family: str = "sans-serif",
    vertical_align: str = "center",
    line_spacing: float = 1.15,
) -> CoverElement:
    return CoverElement(
        id=element_id,
        kind=ElementKind.TEXT,
        region=region,
        transform=ElementTransform(
            rect.x_mm,
            rect.y_mm,
            rect.width_mm,
            rect.height_mm,
            rotation_deg,
        ),
        z_index=z_index,
        content={
            "text": text,
            "font_family": font_family,
            "font_role": font_role,
            "font_size_pt": font_size_pt,
            "font_weight": font_weight,
            "color": color,
            "align": align,
            "vertical_align": vertical_align,
            "line_spacing": line_spacing,
            "direction": "horizontal",
        },
    )


def _shape_element(
    element_id: str,
    region: Region,
    rect: RectMm,
    fill: str,
    *,
    z_index: int = 0,
) -> CoverElement:
    return CoverElement(
        id=element_id,
        kind=ElementKind.SHAPE,
        region=region,
        transform=ElementTransform(
            rect.x_mm,
            rect.y_mm,
            rect.width_mm,
            rect.height_mm,
        ),
        z_index=z_index,
        content={"shape": "rectangle", "fill": fill, "stroke": None},
    )


def _vertical_slice(rect: RectMm, top_fraction: float, height_fraction: float) -> RectMm:
    return RectMm(
        rect.x_mm,
        rect.y_mm + rect.height_mm * top_fraction,
        rect.width_mm,
        rect.height_mm * height_fraction,
    )


def _standard_panel_elements(project: CoverProject, layout: CoverLayout) -> tuple[CoverElement, ...]:
    front_title = _vertical_slice(layout.front_safe_rect, 0.10, 0.32)
    front_author = _vertical_slice(layout.front_safe_rect, 0.48, 0.12)
    back_description = _vertical_slice(layout.back_safe_rect, 0.08, 0.55)
    back_publisher = _vertical_slice(layout.back_safe_rect, 0.72, 0.10)
    back_isbn = _vertical_slice(layout.back_safe_rect, 0.85, 0.10)

    isbn_text = project.metadata.isbn or "ISBN"
    return (
        text_element(
            "front-title",
            Region.FRONT,
            front_title,
            project.metadata.title,
            24.0,
            font_weight=700,
        ),
        text_element(
            "front-author",
            Region.FRONT,
            front_author,
            project.metadata.author,
            12.0,
        ),
        text_element(
            "back-description",
            Region.BACK,
            back_description,
            project.metadata.description,
            10.0,
            align="left",
        ),
        text_element(
            "back-publisher",
            Region.BACK,
            back_publisher,
            project.metadata.publisher,
            8.0,
            align="left",
        ),
        CoverElement(
            id="back-isbn",
            kind=ElementKind.BARCODE_PLACEHOLDER,
            region=Region.BACK,
            transform=ElementTransform(
                back_isbn.x_mm,
                back_isbn.y_mm,
                back_isbn.width_mm,
                back_isbn.height_mm,
            ),
            z_index=10,
            content={"text": isbn_text, "color": "#111111", "align": "left"},
        ),
    )


def _spine_elements(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[tuple[CoverElement, ...], tuple[str, ...]]:
    width = layout.spine_rect.width_mm
    if width < 2.0:
        return (), ("書脊小於 2 mm，已省略書脊文字。",)

    safe = layout.spine_safe_rect
    if width < 4.0:
        title_rect = safe
    else:
        title_rect = _vertical_slice(safe, 0.04, 0.68)

    elements: list[CoverElement] = [
        text_element(
            "spine-title",
            Region.SPINE,
            title_rect,
            project.metadata.title,
            6.0 if width < 4.0 else 8.0,
            rotation_deg=90.0,
            font_weight=600,
        )
    ]
    if width >= 4.0 and project.metadata.author:
        author_rect = _vertical_slice(safe, 0.76, 0.20)
        elements.append(
            text_element(
                "spine-author",
                Region.SPINE,
                author_rect,
                project.metadata.author,
                6.0,
                rotation_deg=90.0,
            )
        )
    return tuple(elements), ()


def _source_cover_only(
    project: CoverProject, layout: CoverLayout
) -> tuple[CoverElement, ...]:
    return ()


def _minimal_text(project: CoverProject, layout: CoverLayout) -> tuple[CoverElement, ...]:
    return ()


def _front_image_plain_back(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CoverElement, ...]:
    return (
        _shape_element(
            "template-front-image-placeholder",
            Region.FRONT,
            layout.front_rect,
            "#E8E8E8",
            z_index=-10,
        ),
        _shape_element(
            "template-back-background",
            Region.BACK,
            layout.back_rect,
            "#F7F7F7",
            z_index=-10,
        ),
    )


def _full_spread(project: CoverProject, layout: CoverLayout) -> tuple[CoverElement, ...]:
    return (
        _shape_element(
            "template-full-spread-placeholder",
            Region.SPREAD,
            layout.bleed_rect,
            "#E5E5E5",
            z_index=-20,
        ),
    )


def _top_bottom_blocks(project: CoverProject, layout: CoverLayout) -> tuple[CoverElement, ...]:
    top_height = max(12.0, layout.front_rect.height_mm * 0.28)
    bottom_height = max(10.0, layout.back_rect.height_mm * 0.18)
    return (
        _shape_element(
            "template-front-top-block",
            Region.FRONT,
            RectMm(
                layout.front_rect.x_mm,
                layout.front_rect.y_mm,
                layout.front_rect.width_mm,
                top_height,
            ),
            "#E2E2E2",
            z_index=-10,
        ),
        _shape_element(
            "template-back-bottom-block",
            Region.BACK,
            RectMm(
                layout.back_rect.x_mm,
                layout.back_rect.bottom_mm - bottom_height,
                layout.back_rect.width_mm,
                bottom_height,
            ),
            "#E2E2E2",
            z_index=-10,
        ),
    )


def _publisher_logo_rect(layout: CoverLayout) -> RectMm:
    safe = layout.back_safe_rect
    return RectMm(
        safe.x_mm + safe.width_mm * 0.26,
        safe.y_mm + safe.height_mm * 0.34,
        safe.width_mm * 0.48,
        safe.height_mm * 0.36,
    )


def _publisher_back_matter_only(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CoverElement, ...]:
    safe = layout.back_safe_rect
    elements: list[CoverElement] = []
    isbn = normalize_isbn(project.metadata.isbn)
    if len(isbn) == 13:
        label_rect = RectMm(
            safe.x_mm + safe.width_mm * 0.03,
            safe.y_mm + safe.height_mm * 0.025,
            safe.width_mm * 0.39,
            safe.height_mm * 0.028,
        )
        barcode_rect = RectMm(
            safe.x_mm + safe.width_mm * 0.03,
            safe.y_mm + safe.height_mm * 0.060,
            safe.width_mm * 0.44,
            safe.height_mm * 0.125,
        )
        elements.append(
            text_element(
                "back-isbn-label",
                Region.BACK,
                label_rect,
                f"ISBN {isbn[:3]}-{isbn[3:6]}-{isbn[6:9]}-{isbn[9:12]}-{isbn[12]}",
                7.0,
                align="left",
                z_index=20,
                font_role="ocr",
                font_family="OCR-B",
                vertical_align="top",
            )
        )
        elements.append(
            CoverElement(
                id="back-isbn-code",
                kind=ElementKind.BARCODE_PLACEHOLDER,
                region=Region.BACK,
                transform=ElementTransform(
                    barcode_rect.x_mm,
                    barcode_rect.y_mm,
                    barcode_rect.width_mm,
                    barcode_rect.height_mm,
                ),
                z_index=20,
                content={
                    "isbn": isbn,
                    "addon": normalize_ean_addon(project.metadata.isbn_addon),
                    "text": isbn,
                    "font_role": "ocr",
                    "font_family": "OCR-B",
                    "color": "#111111",
                    "align": "left",
                },
            )
        )

    info_x = safe.x_mm + safe.width_mm * 0.49
    info_y = safe.y_mm + safe.height_mm * 0.025
    info_width = safe.width_mm * 0.38
    info_layout = layout_publisher_info(
        metadata=project.metadata,
        x_mm=info_x,
        y_mm=info_y,
        max_width_mm=info_width,
        max_height_mm=max(1.0, safe.bottom_mm - info_y),
    )
    shared_content = {
        "group_id": "publisher-info-stack",
        "layout_warnings": list(info_layout.warnings),
    }
    if info_layout.heading_rect is not None:
        heading = text_element(
            "back-publisher-heading",
            Region.BACK,
            info_layout.heading_rect,
            info_layout.heading_text,
            info_layout.heading_font_pt,
            align="left",
            font_weight=500,
            z_index=20,
            font_role="publisher_heading",
            font_family="DFPYuanW5-GB",
            vertical_align="top",
        )
        elements.append(
            replace(
                heading,
                content={
                    **heading.content,
                    **shared_content,
                    "layout_role": "heading",
                },
            )
        )

    if info_layout.details_rect is not None:
        details = text_element(
            "back-publisher-details",
            Region.BACK,
            info_layout.details_rect,
            "\n".join(info_layout.detail_lines),
            info_layout.details_font_pt,
            align="left",
            z_index=20,
            font_role="publisher_details",
            font_family="DFPYuanW3-GB",
            vertical_align="top",
            line_spacing=1.12,
        )
        elements.append(
            replace(
                details,
                content={
                    **details.content,
                    **shared_content,
                    "layout_role": "details",
                    "line_spacing_mm": info_layout.details_line_spacing_mm,
                },
            )
        )
    return tuple(elements)


def _publisher_spine_elements(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CoverElement, ...]:
    spine = layout.spine_rect
    elements: list[CoverElement] = [
        _shape_element(
            "spine-background",
            Region.SPINE,
            spine,
            "#ffffff",
            z_index=-5,
        )
    ]
    accent = project.metadata.spine_accent_color.strip() or "#F15A24"
    _tier, slots = build_spine_slots(layout, accent)
    values = {
        "spine-title-main": project.metadata.title,
        "spine-title-english": project.metadata.english_title,
        "spine-volume": project.metadata.volume_number,
        "spine-arc": project.metadata.arc_label,
        "spine-author": project.metadata.author,
        "spine-internal-code": project.metadata.internal_book_code,
        "spine-publisher-name": project.metadata.publisher,
    }
    for slot in slots:
        text = str(values.get(slot.element_id, "")).strip()
        if not text:
            continue
        element = text_element(
            slot.element_id,
            Region.SPINE,
            slot.rect,
            text,
            slot.font_size_pt,
            rotation_deg=90.0,
            font_weight=slot.font_weight,
            color=slot.color,
            z_index=20,
            font_role=(
                "publisher_heading"
                if slot.role == "publisher"
                else "default"
            ),
            vertical_align="center",
        )
        elements.append(
            replace(
                element,
                content={
                    **element.content,
                    "group_id": "publisher-spine-stack",
                    "layout_role": slot.role,
                },
            )
        )
    logo = project.metadata.publisher_logo
    if logo is not None and logo.path and Path(logo.path).is_file():
        logo_rect = _vertical_slice(layout.spine_safe_rect, 0.01, 0.13)
        elements.append(
            CoverElement(
                id="spine-publisher-logo",
                kind=ElementKind.IMAGE,
                region=Region.SPINE,
                transform=ElementTransform(
                    logo_rect.x_mm,
                    logo_rect.y_mm,
                    logo_rect.width_mm,
                    logo_rect.height_mm,
                    90.0,
                ),
                z_index=21,
                content={
                    "path": logo.path,
                    "fit": "contain",
                    "group_id": "publisher-spine-stack",
                    "layout_role": "logo",
                },
            )
        )
    return tuple(elements)


def _publisher_back_matter_with_spine(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CoverElement, ...]:
    return _publisher_back_matter_only(project, layout) + _publisher_spine_elements(
        project, layout
    )

_BUILDERS = {
    "source_cover_only": _source_cover_only,
    "minimal_text": _minimal_text,
    "front_image_plain_back": _front_image_plain_back,
    "full_spread": _full_spread,
    "top_bottom_blocks": _top_bottom_blocks,
    "publisher_back_matter_with_spine": _publisher_back_matter_with_spine,
}

_TEMPLATE_ALIASES = {
    "minimal": "source_cover_only",
    "classic_book": "minimal_text",
    "full_bleed_image": "full_spread",
    "publisher_back_matter": "publisher_back_matter_with_spine",
}


def apply_template(project: CoverProject, template_id: str) -> CoverProject:
    canonical_template_id = _TEMPLATE_ALIASES.get(template_id, template_id)
    try:
        builder = _BUILDERS[canonical_template_id]
    except KeyError as exc:
        raise ValueError(f"未知封面模板：{template_id}") from exc

    layout = calculate_layout(project)
    retained = tuple(
        element
        for element in project.elements
        if element.id not in STANDARD_TEMPLATE_IDS
        and not element.id.startswith("template-")
    )
    standard_elements = _standard_panel_elements(project, layout)
    has_front_image = any(
        element.kind is ElementKind.IMAGE
        and element.region in {Region.FRONT, Region.SPREAD}
        and isinstance(element.content.get("path"), str)
        and bool(str(element.content.get("path", "")).strip())
        for element in retained
    )
    if canonical_template_id == "front_image_plain_back":
        standard_elements = tuple(
            element for element in standard_elements if element.region is Region.BACK
        )
    elif canonical_template_id == "publisher_back_matter_with_spine":
        standard_elements = tuple(
            element
            for element in standard_elements
            if element.region is not Region.BACK
            and not (has_front_image and element.region is Region.FRONT)
        )
    elif canonical_template_id in {"source_cover_only", "full_spread"}:
        standard_elements = ()

    if canonical_template_id in {
        "source_cover_only",
        "full_spread",
        "publisher_back_matter_with_spine",
    }:
        spine_elements, new_warnings = (), ()
    else:
        spine_elements, new_warnings = _spine_elements(project, layout)
    generated = builder(project, layout) + standard_elements + spine_elements

    background = dict(project.background)
    warnings = list(background.get("warnings", ()))
    for warning in new_warnings:
        if warning not in warnings:
            warnings.append(warning)
    for element in generated:
        layout_warnings = element.content.get("layout_warnings", ())
        if not isinstance(layout_warnings, (list, tuple)):
            continue
        for warning in layout_warnings:
            text = str(warning).strip()
            if text and text not in warnings:
                warnings.append(text)
    if warnings:
        background["warnings"] = warnings
    else:
        background.pop("warnings", None)
    background["active_template"] = canonical_template_id
    if canonical_template_id == "publisher_back_matter_with_spine":
        logo = _publisher_logo_rect(layout)
        background.setdefault("color", "#ffffff")
        background["publisher_logo_slot"] = {
            "x_mm": logo.x_mm,
            "y_mm": logo.y_mm,
            "width_mm": logo.width_mm,
            "height_mm": logo.height_mm,
        }
    else:
        background.pop("publisher_logo_slot", None)

    if canonical_template_id == "full_spread":
        image_mode = ImageMode.FULL_SPREAD
    elif project.image_mode is ImageMode.SEPARATE_COVERS:
        image_mode = ImageMode.SEPARATE_COVERS
    else:
        image_mode = ImageMode.FRONT_ONLY
    return replace(
        project,
        image_mode=image_mode,
        background=background,
        elements=retained + generated,
    )


def refresh_template_metadata(
    project: CoverProject,
    metadata,
    *,
    reset_layout: bool = False,
) -> CoverProject:
    """Refresh template-managed content while preserving edited geometry."""

    candidate = replace(project, metadata=metadata)
    active = str(project.background.get("active_template", "")).strip()
    if not active:
        return candidate
    canonical = _TEMPLATE_ALIASES.get(active, active)
    if reset_layout:
        return apply_template(candidate, canonical)

    generated = apply_template(candidate, canonical)
    old_by_id = project.elements_by_id
    generated_ids = {element.id for element in generated.elements}
    merged: list[CoverElement] = []
    for element in generated.elements:
        old = old_by_id.get(element.id)
        if old is None or element.id not in STANDARD_TEMPLATE_IDS:
            merged.append(element)
            continue
        old_content = dict(old.content)
        was_hidden = bool(old_content.get("template_hidden", False))
        opacity = float(old_content.get("template_saved_opacity", 1.0)) if was_hidden else old.opacity
        content = dict(element.content)
        content.pop("template_hidden", None)
        content.pop("template_saved_opacity", None)
        merged.append(
            replace(
                element,
                transform=old.transform,
                z_index=old.z_index,
                opacity=opacity,
                content=content,
            )
        )

    for old in project.elements:
        if old.id not in STANDARD_TEMPLATE_IDS or old.id in generated_ids:
            continue
        content = dict(old.content)
        content["template_hidden"] = True
        content.setdefault("template_saved_opacity", old.opacity)
        merged.append(replace(old, opacity=0.0, content=content))

    return replace(generated, elements=tuple(merged))
