from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    Region,
)


_ALLOWED_ELEMENT_PATCHES = {
    "transform",
    "content",
    "kind",
    "region",
    "z_index",
    "opacity",
}
_ALLOWED_TRANSFORM_PATCHES = {
    "x_mm",
    "y_mm",
    "width_mm",
    "height_mm",
    "rotation_deg",
}


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} 必須是物件。")
    return value


def _patch_transform(
    transform: ElementTransform,
    patch: object,
) -> ElementTransform:
    values = _mapping(patch, "transform patch")
    unknown = sorted(set(values) - _ALLOWED_TRANSFORM_PATCHES)
    if unknown:
        raise ValueError("不支援的 transform 欄位：" + "、".join(unknown))
    updates = {name: float(value) for name, value in values.items()}
    return replace(transform, **updates)


def _patch_cover_element(element: CoverElement, patch: Mapping[str, Any]) -> CoverElement:
    unknown = sorted(set(patch) - _ALLOWED_ELEMENT_PATCHES)
    if unknown:
        raise ValueError("不支援的元素欄位：" + "、".join(unknown))

    updates: dict[str, Any] = {}
    if "transform" in patch:
        updates["transform"] = _patch_transform(element.transform, patch["transform"])
    if "content" in patch:
        content_patch = _mapping(patch["content"], "content patch")
        content = dict(element.content)
        content.update(content_patch)
        updates["content"] = content
    if "kind" in patch:
        updates["kind"] = ElementKind(str(patch["kind"]))
    if "region" in patch:
        updates["region"] = Region(str(patch["region"]))
    if "z_index" in patch:
        updates["z_index"] = int(patch["z_index"])
    if "opacity" in patch:
        updates["opacity"] = float(patch["opacity"])
    return replace(element, **updates)


def patch_element(
    project: CoverProject,
    element_id: str,
    patch: Mapping[str, Any],
) -> CoverProject:
    if not element_id.strip():
        raise ValueError("元素 id 不可為空。")
    values = _mapping(patch, "元素 patch")
    found = False
    elements: list[CoverElement] = []
    for element in project.elements:
        if element.id == element_id:
            found = True
            elements.append(_patch_cover_element(element, values))
        else:
            elements.append(element)
    if not found:
        raise KeyError(f"找不到封面元素：{element_id}")
    return replace(project, elements=tuple(elements))
