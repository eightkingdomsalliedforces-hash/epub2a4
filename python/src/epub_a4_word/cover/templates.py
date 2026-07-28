from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

from .geometry import CoverLayout, RectMm, calculate_layout
from .isbn import normalize_ean_addon, normalize_isbn
from .modern_spine_layout import build_modern_spine_slots
from .publisher_info_layout import layout_publisher_info
from .spine_layout import build_spine_slots
from .vertical_copy_layout import layout_vertical_copy
from .models import (
    CoverElement,
    LogoAssetMetadata,
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
    TemplateSummary(
        "modern_vertical_back_with_spine",
        "現代直排封底＋可選書脊",
        "可編輯直排內文、醒目文案與三種書脊。",
    ),
)

STANDARD_TEMPLATE_IDS = frozenset(
    {
        "front-title",
        "front-author",
        "spine-title",
        "spine-author",
        "spine-publisher",
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
        "back-publisher-logo",
    }
)

_MODERN_TEMPLATE_PREFIXES = (
    "modern-back-copy-column-",
    "modern-back-copy-separator-",
    "modern-back-highlight-column-",
    "modern-back-highlight-separator-",
    "modern-spine-",
)


def _is_template_managed_id(element_id: str) -> bool:
    return element_id in STANDARD_TEMPLATE_IDS or element_id.startswith(
        _MODERN_TEMPLATE_PREFIXES
    )


def list_templates() -> tuple[TemplateSummary, ...]:
    return _TEMPLATE_CATALOG


def assign_publisher_logo(project: CoverProject, path: Path | str) -> CoverProject:
    """Apply a manually selected publisher Logo through the shared metadata model."""
    resolved_path = str(Path(path).expanduser().resolve())
    metadata = replace(
        project.metadata,
        publisher_logo=LogoAssetMetadata(
            asset_id=f"publisher-logo-{Path(resolved_path).stem}",
            path=resolved_path,
            source_category="manual",
            manual_selection=True,
        ),
    )
    return refresh_template_metadata(project, metadata)


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
        title_rect = _vertical_slice(
            safe,
            0.14 if width >= 6.0 else 0.04,
            0.48 if width >= 6.0 else 0.68,
        )

    title_is_cjk = bool(re.search(r"[\u3400-\u9fff]", project.metadata.title))
    elements: list[CoverElement] = [
        text_element(
            "spine-title",
            Region.SPINE,
            title_rect,
            project.metadata.title,
            8.0 if width < 8.0 else (12.0 if width < 10.0 else 14.0),
            rotation_deg=0.0 if title_is_cjk else 90.0,
            font_weight=600,
        )
    ]
    elements[0] = replace(
        elements[0],
        content={
            **elements[0].content,
            "direction": "vertical" if title_is_cjk else "horizontal",
        },
    )
    if width >= 4.0 and project.metadata.author:
        author_rect = _vertical_slice(
            safe, 0.64 if width >= 6.0 else 0.76, 0.18
        )
        author_is_cjk = bool(re.search(r"[\u3400-\u9fff]", project.metadata.author))
        author = text_element(
                "spine-author",
                Region.SPINE,
                author_rect,
                project.metadata.author,
                8.0 if width < 8.0 else (9.0 if width < 10.0 else 10.0),
                rotation_deg=0.0 if author_is_cjk else 90.0,
            )
        elements.append(
            replace(
                author,
                content={
                    **author.content,
                    "direction": "vertical" if author_is_cjk else "horizontal",
                },
            )
        )
    if width >= 6.0 and project.metadata.publisher:
        publisher = text_element(
            "spine-publisher",
            Region.SPINE,
            _vertical_slice(safe, 0.84, 0.12),
            project.metadata.publisher,
            8.0 if width < 8.0 else (9.0 if width < 10.0 else 10.0),
            font_weight=600,
        )
        elements.append(
            replace(
                publisher,
                content={**publisher.content, "direction": "vertical"},
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
    logo = project.metadata.publisher_logo
    if logo is not None and logo.path and Path(logo.path).is_file():
        logo_rect = _publisher_logo_rect(layout)
        elements.append(
            CoverElement(
                id="back-publisher-logo",
                kind=ElementKind.IMAGE,
                region=Region.BACK,
                transform=ElementTransform(
                    logo_rect.x_mm,
                    logo_rect.y_mm,
                    logo_rect.width_mm,
                    logo_rect.height_mm,
                ),
                z_index=21,
                content={
                    "path": logo.path,
                    "fit": "contain",
                    "group_id": "publisher-info-stack",
                    "layout_role": "logo",
                    "clip_to_region": True,
                },
            )
        )
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
        use_vertical = slot.role != "english" and bool(
            re.search(r"[\u3400-\u9fff]", text)
        )
        element = text_element(
            slot.element_id,
            Region.SPINE,
            slot.rect,
            text,
            slot.font_size_pt,
            rotation_deg=0.0 if use_vertical else 90.0,
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
                    "direction": "vertical" if use_vertical else "horizontal",
                },
            )
        )
    logo = project.metadata.publisher_logo
    if logo is not None and logo.path and Path(logo.path).is_file():
        logo_width = layout.spine_rect.width_mm * 0.90
        logo_height = min(18.0, layout.spine_safe_rect.height_mm * 0.10)
        logo_rect = RectMm(
            layout.spine_rect.x_mm + (layout.spine_rect.width_mm - logo_width) / 2.0,
            layout.spine_safe_rect.y_mm,
            logo_width,
            logo_height,
        )
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
                    0.0,
                ),
                z_index=21,
                content={
                    "path": logo.path,
                    "fit": "contain",
                    "group_id": "publisher-spine-stack",
                    "layout_role": "logo",
                    "clip_to_region": True,
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


def _modern_vertical_columns(
    *,
    text: str,
    target: RectMm,
    prefix: str,
    color: str,
    preferred_font_pt: float,
    minimum_font_pt: float,
    maximum_columns: int,
) -> tuple[CoverElement, ...]:
    if not text.strip():
        return ()
    result = layout_vertical_copy(
        text,
        target,
        preferred_font_pt=preferred_font_pt,
        minimum_font_pt=minimum_font_pt,
        preferred_gap_mm=2.0,
        maximum_columns=maximum_columns,
    )
    elements: list[CoverElement] = []
    for index, column in enumerate(result.columns, start=1):
        element = text_element(
            f"{prefix}-column-{index}",
            Region.BACK,
            column.rect,
            column.text,
            column.font_size_pt,
            align="center",
            font_weight=500 if "highlight" in prefix else 400,
            color=color,
            z_index=20,
            font_family="DFPYuanW5-GB" if "highlight" in prefix else "DFPYuanW3-GB",
            vertical_align="top",
            line_spacing=1.0,
        )
        elements.append(
            replace(
                element,
                content={
                    **element.content,
                    "direction": "vertical",
                    "group_id": "modern-back-copy",
                    "layout_role": (
                        "highlight-copy" if "highlight" in prefix else "body-copy"
                    ),
                    "layout_warnings": list(result.warnings) if index == 1 else [],
                },
            )
        )
    for index, separator in enumerate(result.separators, start=1):
        elements.append(
            _shape_element(
                f"{prefix}-separator-{index}",
                Region.BACK,
                separator,
                color if "highlight" in prefix else "#B8B8B8",
                z_index=19,
            )
        )
    return tuple(elements)


def _modern_vertical_back(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CoverElement, ...]:
    safe = layout.back_safe_rect
    top_limit = safe.y_mm + safe.height_mm * 0.20
    allowed_top_ids = {
        "back-isbn-label",
        "back-isbn-code",
        "back-publisher-heading",
        "back-publisher-details",
    }
    top_elements: list[CoverElement] = []
    for element in _publisher_back_matter_only(project, layout):
        if element.id not in allowed_top_ids:
            continue
        available_height = top_limit - element.transform.y_mm
        if available_height <= 0:
            continue
        if element.transform.height_mm > available_height:
            element = replace(
                element,
                transform=replace(
                    element.transform,
                    height_mm=available_height,
                ),
            )
        top_elements.append(element)

    body_target = RectMm(
        safe.x_mm + safe.width_mm * 0.05,
        safe.y_mm + safe.height_mm * 0.24,
        safe.width_mm * 0.61,
        safe.height_mm * 0.62,
    )
    highlight_target = RectMm(
        safe.x_mm + safe.width_mm * 0.69,
        safe.y_mm + safe.height_mm * 0.24,
        safe.width_mm * 0.27,
        safe.height_mm * 0.62,
    )
    accent = project.metadata.spine_accent_color.strip() or "#F15A24"
    body = _modern_vertical_columns(
        text=project.metadata.back_vertical_copy,
        target=body_target,
        prefix="modern-back-copy",
        color="#242424",
        preferred_font_pt=10.0,
        minimum_font_pt=7.0,
        maximum_columns=10,
    )
    highlight = _modern_vertical_columns(
        text=project.metadata.back_highlight_copy,
        target=highlight_target,
        prefix="modern-back-highlight",
        color=accent,
        preferred_font_pt=15.0,
        minimum_font_pt=9.0,
        maximum_columns=5,
    )
    return (
        *top_elements,
        *body,
        *highlight,
        *_modern_spine_elements(project, layout),
    )


def _modern_spine_elements(
    project: CoverProject,
    layout: CoverLayout,
) -> tuple[CoverElement, ...]:
    metadata = project.metadata
    accent = metadata.spine_accent_color.strip() or "#F15A24"
    spine_layout = build_modern_spine_slots(
        layout,
        metadata.spine_style,
        accent,
    )
    elements: list[CoverElement] = [
        _shape_element(
            "modern-spine-background",
            Region.SPINE,
            layout.spine_rect,
            "#FFFFFF",
            z_index=-5,
        )
    ]
    values = {
        "title": metadata.title,
        "english_title": metadata.english_title,
        "arc": metadata.arc_label,
        "volume_badge": metadata.volume_number,
        "author": metadata.author,
        "code": metadata.internal_book_code,
        "publisher": metadata.publisher,
    }
    for slot in spine_layout.slots:
        if slot.role == "logo":
            logo = metadata.publisher_logo
            if logo is None or not logo.path or not Path(logo.path).is_file():
                continue
            elements.append(
                CoverElement(
                    id=slot.element_id,
                    kind=ElementKind.IMAGE,
                    region=Region.SPINE,
                    transform=ElementTransform(
                        slot.rect.x_mm,
                        slot.rect.y_mm,
                        slot.rect.width_mm,
                        slot.rect.height_mm,
                    ),
                    z_index=22,
                    content={
                        "path": logo.path,
                        "fit": "contain",
                        "group_id": "modern-spine-stack",
                        "layout_role": "logo",
                        "clip_to_region": True,
                    },
                )
            )
            continue

        value = str(values.get(slot.role, "")).strip()
        if not value:
            continue
        if slot.role == "volume_badge":
            diameter = min(slot.rect.width_mm, slot.rect.height_mm)
            badge = RectMm(
                slot.rect.x_mm + (slot.rect.width_mm - diameter) / 2.0,
                slot.rect.y_mm + (slot.rect.height_mm - diameter) / 2.0,
                diameter,
                diameter,
            )
            elements.append(
                CoverElement(
                    id="modern-spine-volume-badge",
                    kind=ElementKind.SHAPE,
                    region=Region.SPINE,
                    transform=ElementTransform(
                        badge.x_mm,
                        badge.y_mm,
                        badge.width_mm,
                        badge.height_mm,
                    ),
                    z_index=20,
                    content={
                        "shape": "ellipse",
                        "fill": "#FFFFFF",
                        "stroke": accent,
                        "stroke_width": 0.45,
                        "group_id": "modern-spine-stack",
                        "layout_role": "volume-badge",
                    },
                )
            )
            target = badge
        else:
            target = slot.rect
        element = text_element(
            slot.element_id,
            Region.SPINE,
            target,
            value,
            slot.font_size_pt,
            align="center",
            rotation_deg=90.0 if slot.direction == "horizontal" else 0.0,
            font_weight=slot.font_weight,
            color=slot.color,
            z_index=21,
            font_family=(
                "sans-serif" if slot.direction == "horizontal" else "DFPYuanW5-GB"
            ),
            vertical_align="center",
            line_spacing=1.0,
        )
        elements.append(
            replace(
                element,
                content={
                    **element.content,
                    "direction": slot.direction,
                    "group_id": "modern-spine-stack",
                    "layout_role": slot.role,
                    "layout_warnings": (
                        list(spine_layout.warnings)
                        if slot.role == "title"
                        else []
                    ),
                },
            )
        )
    return tuple(elements)


_BUILDERS = {
    "source_cover_only": _source_cover_only,
    "minimal_text": _minimal_text,
    "front_image_plain_back": _front_image_plain_back,
    "full_spread": _full_spread,
    "top_bottom_blocks": _top_bottom_blocks,
    "publisher_back_matter_with_spine": _publisher_back_matter_with_spine,
    "modern_vertical_back_with_spine": _modern_vertical_back,
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
        if not _is_template_managed_id(element.id)
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
    elif canonical_template_id in {
        "publisher_back_matter_with_spine",
        "modern_vertical_back_with_spine",
    }:
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
        "modern_vertical_back_with_spine",
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

    if (
        metadata.extracted_accent_color
        and metadata.spine_accent_color != metadata.extracted_accent_color
    ):
        metadata = replace(metadata, accent_color_mode="manual")
    candidate = replace(project, metadata=metadata)
    active = str(project.background.get("active_template", "")).strip()
    if not active:
        return candidate
    canonical = _TEMPLATE_ALIASES.get(active, active)
    if reset_layout:
        return apply_template(candidate, canonical)

    generated = apply_template(candidate, canonical)
    old_by_id = project.elements_by_id
    generated_by_id = generated.elements_by_id
    old_heading = old_by_id.get("back-publisher-heading")
    generated_heading = generated_by_id.get("back-publisher-heading")
    heading_growth = 0.0
    if old_heading is not None and generated_heading is not None:
        heading_growth = max(
            0.0,
            generated_heading.transform.height_mm
            - old_heading.transform.height_mm,
        )
    generated_ids = {element.id for element in generated.elements}
    spine_style_changed = metadata.spine_style != project.metadata.spine_style
    merged: list[CoverElement] = []
    for element in generated.elements:
        old = old_by_id.get(element.id)
        if spine_style_changed and element.id.startswith("modern-spine-"):
            old = None
        if old is None or not _is_template_managed_id(element.id):
            merged.append(element)
            continue
        old_content = dict(old.content)
        was_hidden = bool(old_content.get("template_hidden", False))
        opacity = float(old_content.get("template_saved_opacity", 1.0)) if was_hidden else old.opacity
        content = dict(element.content)
        content.pop("template_hidden", None)
        content.pop("template_saved_opacity", None)
        transform = old.transform
        if element.id == "back-publisher-heading":
            transform = replace(
                old.transform,
                height_mm=max(
                    old.transform.height_mm,
                    element.transform.height_mm,
                ),
            )
        elif element.id == "back-publisher-details":
            transform = replace(
                old.transform,
                y_mm=old.transform.y_mm + heading_growth,
                height_mm=max(
                    old.transform.height_mm,
                    element.transform.height_mm,
                ),
            )
        merged.append(
            replace(
                element,
                transform=transform,
                z_index=old.z_index,
                opacity=opacity,
                content=content,
            )
        )

    for old in project.elements:
        if not _is_template_managed_id(old.id) or old.id in generated_ids:
            continue
        content = dict(old.content)
        content["template_hidden"] = True
        content.setdefault("template_saved_opacity", old.opacity)
        merged.append(replace(old, opacity=0.0, content=content))

    return replace(generated, elements=tuple(merged))
