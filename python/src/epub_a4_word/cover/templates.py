from __future__ import annotations

from dataclasses import dataclass, replace

from .geometry import CoverLayout, RectMm, calculate_layout
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
)

STANDARD_TEMPLATE_IDS = frozenset(
    {
        "front-title",
        "front-author",
        "spine-title",
        "spine-author",
        "back-description",
        "back-publisher",
        "back-isbn",
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
            "font_family": "sans-serif",
            "font_size_pt": font_size_pt,
            "font_weight": font_weight,
            "color": color,
            "align": align,
            "line_spacing": 1.15,
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


_BUILDERS = {
    "source_cover_only": _source_cover_only,
    "minimal_text": _minimal_text,
    "front_image_plain_back": _front_image_plain_back,
    "full_spread": _full_spread,
    "top_bottom_blocks": _top_bottom_blocks,
}

_TEMPLATE_ALIASES = {
    "minimal": "source_cover_only",
    "classic_book": "minimal_text",
    "full_bleed_image": "full_spread",
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
    if canonical_template_id == "front_image_plain_back":
        standard_elements = tuple(
            element for element in standard_elements if element.region is Region.BACK
        )
    elif canonical_template_id in {"source_cover_only", "full_spread"}:
        standard_elements = ()

    if canonical_template_id in {"source_cover_only", "full_spread"}:
        spine_elements, new_warnings = (), ()
    else:
        spine_elements, new_warnings = _spine_elements(project, layout)
    generated = builder(project, layout) + standard_elements + spine_elements

    background = dict(project.background)
    warnings = list(background.get("warnings", ()))
    for warning in new_warnings:
        if warning not in warnings:
            warnings.append(warning)
    if warnings:
        background["warnings"] = warnings
    else:
        background.pop("warnings", None)

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
