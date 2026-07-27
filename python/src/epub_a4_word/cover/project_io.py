from __future__ import annotations

import json
import math
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .models import (
    CoverElement,
    CoverMetadata,
    CoverProject,
    ElementKind,
    ElementTransform,
    ExportSettings,
    ImageMode,
    LogoAssetMetadata,
    Region,
    TrimSize,
)


class CoverValidationError(ValueError):
    """Raised when schema or physical cover values are invalid."""


def dumps_project(project: CoverProject) -> str:
    validate_project(project)
    try:
        return json.dumps(
            _to_json_value(project),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise CoverValidationError(f"封面專案包含無法序列化的值：{exc}") from exc


def loads_project(json_text: str) -> CoverProject:
    try:
        raw = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise CoverValidationError(f"封面專案 JSON 無效：{exc.msg}") from exc
    project = _project_from_dict(raw)
    validate_project(project)
    return project


def validate_project(project: CoverProject) -> None:
    if not isinstance(project, CoverProject):
        raise CoverValidationError("封面專案型別無效。")
    if project.schema_version != 1:
        raise CoverValidationError("不支援的 schema_version")
    _require_non_empty_text(project.source_file, "source_file")
    _require_non_empty_text(project.source_type, "source_type")
    if not isinstance(project.working_dir, str):
        raise CoverValidationError("working_dir 必須是字串。")
    if not _is_int(project.page_count) or project.page_count < 1:
        raise CoverValidationError("page_count 必須大於 0")
    _require_positive_number(project.trim_size.width_mm, "trim_size.width_mm")
    _require_positive_number(project.trim_size.height_mm, "trim_size.height_mm")
    _require_positive_number(project.paper_caliper_mm, "paper_caliper_mm")
    if project.manual_spine_width_mm is not None:
        _require_positive_number(project.manual_spine_width_mm, "manual_spine_width_mm")
    if not _is_finite_number(project.bleed_mm) or not 0.0 <= float(project.bleed_mm) <= 10.0:
        raise CoverValidationError("bleed_mm 必須介於 0 與 10")
    if not _is_finite_number(project.overlap_mm) or float(project.overlap_mm) != 5.0:
        raise CoverValidationError("第一版 overlap_mm 必須為 5")
    if not isinstance(project.image_mode, ImageMode):
        raise CoverValidationError("image_mode 無效。")
    _validate_json_mapping(project.background, "background")
    _validate_metadata(project.metadata)
    _validate_export_settings(project.export_settings)

    seen_ids: set[str] = set()
    for element in project.elements:
        if not isinstance(element, CoverElement):
            raise CoverValidationError("elements 包含無效項目。")
        if not isinstance(element.id, str) or not element.id.strip():
            raise CoverValidationError("元素 id 不可為空。")
        if element.id in seen_ids:
            raise CoverValidationError(f"元素 id 重複：{element.id}")
        seen_ids.add(element.id)
        if not isinstance(element.kind, ElementKind):
            raise CoverValidationError(f"元素 {element.id} 的 kind 無效。")
        if not isinstance(element.region, Region):
            raise CoverValidationError(f"元素 {element.id} 的 region 無效。")
        _require_finite_number(element.transform.x_mm, f"元素 {element.id} x_mm")
        _require_finite_number(element.transform.y_mm, f"元素 {element.id} y_mm")
        _require_positive_number(element.transform.width_mm, f"元素 {element.id} 寬高")
        _require_positive_number(element.transform.height_mm, f"元素 {element.id} 寬高")
        _require_finite_number(element.transform.rotation_deg, f"元素 {element.id} rotation_deg")
        if not _is_int(element.z_index):
            raise CoverValidationError(f"元素 {element.id} 的 z_index 必須是整數。")
        if not _is_finite_number(element.opacity) or not 0.0 <= float(element.opacity) <= 1.0:
            raise CoverValidationError(f"元素 {element.id} 的 opacity 必須介於 0 與 1。")
        _validate_json_mapping(element.content, f"元素 {element.id} content")
        if element.kind is ElementKind.IMAGE:
            image_path = element.content.get("path")
            if not isinstance(image_path, str) or not image_path.strip():
                raise CoverValidationError(f"元素 {element.id} 缺少圖片 path。")
            if not Path(image_path).is_file():
                raise CoverValidationError(f"元素 {element.id} 的圖片不存在：{image_path}")


def _validate_metadata(metadata: CoverMetadata) -> None:
    if not isinstance(metadata, CoverMetadata):
        raise CoverValidationError("metadata 型別無效。")
    for name in (
        "title",
        "author",
        "description",
        "isbn",
        "publisher",
        "price",
        "publication_place",
        "translator",
        "isbn_addon",
        "publisher_id",
        "english_title",
        "volume_number",
        "arc_label",
        "series_name",
        "internal_book_code",
        "spine_accent_color",
        "language",
    ):
        if not isinstance(getattr(metadata, name), str):
            raise CoverValidationError(f"metadata.{name} 必須是字串。")
    if metadata.publisher_logo is not None:
        _validate_logo_metadata(metadata.publisher_logo)
    if not isinstance(metadata.page_count_is_estimate, bool):
        raise CoverValidationError("metadata.page_count_is_estimate 必須是布林值。")
    if not isinstance(metadata.embedded_images, tuple):
        raise CoverValidationError("metadata.embedded_images 必須是陣列。")
    for index, item in enumerate(metadata.embedded_images):
        _validate_json_mapping(item, f"metadata.embedded_images[{index}]")



def _validate_logo_metadata(logo: LogoAssetMetadata) -> None:
    if not isinstance(logo, LogoAssetMetadata):
        raise CoverValidationError("metadata.publisher_logo 型別無效。")
    for name in (
        "asset_id",
        "path",
        "source_url",
        "source_category",
        "downloaded_at",
        "image_format",
        "license_text",
    ):
        if not isinstance(getattr(logo, name), str):
            raise CoverValidationError(f"metadata.publisher_logo.{name} 必須是字串。")
    for name in ("width_px", "height_px"):
        value = getattr(logo, name)
        if not _is_int(value) or value < 0:
            raise CoverValidationError(f"metadata.publisher_logo.{name} 必須是非負整數。")
    for name in ("official_source", "manual_selection"):
        if not isinstance(getattr(logo, name), bool):
            raise CoverValidationError(f"metadata.publisher_logo.{name} 必須是布林值。")

def _validate_export_settings(settings: ExportSettings) -> None:
    if not isinstance(settings, ExportSettings):
        raise CoverValidationError("export_settings 型別無效。")
    if not _is_int(settings.dpi) or settings.dpi < 1:
        raise CoverValidationError("export_settings.dpi 必須大於 0。")
    if not isinstance(settings.show_crop_marks, bool):
        raise CoverValidationError("export_settings.show_crop_marks 必須是布林值。")
    if not isinstance(settings.show_assembly_marks, bool):
        raise CoverValidationError("export_settings.show_assembly_marks 必須是布林值。")


def _to_json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _to_json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_to_json_value(item) for item in value]
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    return value


def _project_from_dict(raw: Any) -> CoverProject:
    data = _mapping(raw, "root")
    _keys(
        data,
        required={
            "schema_version",
            "source_file",
            "source_type",
            "metadata",
            "trim_size",
            "page_count",
            "paper_caliper_mm",
            "manual_spine_width_mm",
            "bleed_mm",
            "overlap_mm",
            "image_mode",
        },
        optional={"working_dir", "background", "elements", "export_settings"},
        label="root",
    )
    return CoverProject(
        schema_version=_integer(data["schema_version"], "schema_version"),
        source_file=_string(data["source_file"], "source_file"),
        source_type=_string(data["source_type"], "source_type"),
        metadata=_metadata_from_dict(data["metadata"]),
        trim_size=_trim_size_from_dict(data["trim_size"]),
        page_count=_integer(data["page_count"], "page_count"),
        paper_caliper_mm=_number(data["paper_caliper_mm"], "paper_caliper_mm"),
        manual_spine_width_mm=_optional_number(
            data["manual_spine_width_mm"], "manual_spine_width_mm"
        ),
        bleed_mm=_number(data["bleed_mm"], "bleed_mm"),
        overlap_mm=_number(data["overlap_mm"], "overlap_mm"),
        image_mode=_enum(ImageMode, data["image_mode"], "image_mode"),
        working_dir=_string(data.get("working_dir", ""), "working_dir"),
        background=_plain_dict(data.get("background", {}), "background"),
        elements=tuple(
            _element_from_dict(item, index)
            for index, item in enumerate(_array(data.get("elements", []), "elements"))
        ),
        export_settings=_export_settings_from_dict(data.get("export_settings", {})),
    )


def _metadata_from_dict(raw: Any) -> CoverMetadata:
    data = _mapping(raw, "metadata")
    allowed = {
        "title",
        "author",
        "description",
        "isbn",
        "publisher",
        "price",
        "publication_place",
        "translator",
        "isbn_addon",
        "publisher_id",
        "english_title",
        "volume_number",
        "arc_label",
        "series_name",
        "internal_book_code",
        "spine_accent_color",
        "publisher_logo",
        "language",
        "page_count_is_estimate",
        "embedded_images",
    }
    _keys(data, required=set(), optional=allowed, label="metadata")
    images = _array(data.get("embedded_images", []), "metadata.embedded_images")
    return CoverMetadata(
        title=_string(data.get("title", ""), "metadata.title"),
        author=_string(data.get("author", ""), "metadata.author"),
        description=_string(data.get("description", ""), "metadata.description"),
        isbn=_string(data.get("isbn", ""), "metadata.isbn"),
        publisher=_string(data.get("publisher", ""), "metadata.publisher"),
        price=_string(data.get("price", ""), "metadata.price"),
        publication_place=_string(
            data.get("publication_place", ""), "metadata.publication_place"
        ),
        translator=_string(data.get("translator", ""), "metadata.translator"),
        isbn_addon=_string(data.get("isbn_addon", ""), "metadata.isbn_addon"),
        publisher_id=_string(data.get("publisher_id", ""), "metadata.publisher_id"),
        english_title=_string(data.get("english_title", ""), "metadata.english_title"),
        volume_number=_string(data.get("volume_number", ""), "metadata.volume_number"),
        arc_label=_string(data.get("arc_label", ""), "metadata.arc_label"),
        series_name=_string(data.get("series_name", ""), "metadata.series_name"),
        internal_book_code=_string(
            data.get("internal_book_code", ""), "metadata.internal_book_code"
        ),
        spine_accent_color=_string(
            data.get("spine_accent_color", "#F15A24"),
            "metadata.spine_accent_color",
        ),
        publisher_logo=_logo_metadata_from_dict(data.get("publisher_logo")),
        language=_string(data.get("language", ""), "metadata.language"),
        page_count_is_estimate=_boolean(
            data.get("page_count_is_estimate", False), "metadata.page_count_is_estimate"
        ),
        embedded_images=tuple(
            _plain_dict(item, f"metadata.embedded_images[{index}]")
            for index, item in enumerate(images)
        ),
    )


def _logo_metadata_from_dict(raw: Any) -> LogoAssetMetadata | None:
    if raw is None:
        return None
    data = _mapping(raw, "metadata.publisher_logo")
    allowed = {
        "asset_id",
        "path",
        "source_url",
        "source_category",
        "downloaded_at",
        "image_format",
        "width_px",
        "height_px",
        "license_text",
        "official_source",
        "manual_selection",
    }
    _keys(data, required=set(), optional=allowed, label="metadata.publisher_logo")
    return LogoAssetMetadata(
        asset_id=_string(data.get("asset_id", ""), "metadata.publisher_logo.asset_id"),
        path=_string(data.get("path", ""), "metadata.publisher_logo.path"),
        source_url=_string(
            data.get("source_url", ""), "metadata.publisher_logo.source_url"
        ),
        source_category=_string(
            data.get("source_category", ""),
            "metadata.publisher_logo.source_category",
        ),
        downloaded_at=_string(
            data.get("downloaded_at", ""), "metadata.publisher_logo.downloaded_at"
        ),
        image_format=_string(
            data.get("image_format", ""), "metadata.publisher_logo.image_format"
        ),
        width_px=_integer(data.get("width_px", 0), "metadata.publisher_logo.width_px"),
        height_px=_integer(
            data.get("height_px", 0), "metadata.publisher_logo.height_px"
        ),
        license_text=_string(
            data.get("license_text", ""), "metadata.publisher_logo.license_text"
        ),
        official_source=_boolean(
            data.get("official_source", False),
            "metadata.publisher_logo.official_source",
        ),
        manual_selection=_boolean(
            data.get("manual_selection", False),
            "metadata.publisher_logo.manual_selection",
        ),
    )


def _trim_size_from_dict(raw: Any) -> TrimSize:
    data = _mapping(raw, "trim_size")
    _keys(data, required={"width_mm", "height_mm"}, optional=set(), label="trim_size")
    return TrimSize(
        width_mm=_number(data["width_mm"], "trim_size.width_mm"),
        height_mm=_number(data["height_mm"], "trim_size.height_mm"),
    )


def _element_from_dict(raw: Any, index: int) -> CoverElement:
    label = f"elements[{index}]"
    data = _mapping(raw, label)
    _keys(
        data,
        required={"id", "kind", "region", "transform"},
        optional={"z_index", "opacity", "content"},
        label=label,
    )
    return CoverElement(
        id=_string(data["id"], f"{label}.id"),
        kind=_enum(ElementKind, data["kind"], f"{label}.kind"),
        region=_enum(Region, data["region"], f"{label}.region"),
        transform=_transform_from_dict(data["transform"], f"{label}.transform"),
        z_index=_integer(data.get("z_index", 0), f"{label}.z_index"),
        opacity=_number(data.get("opacity", 1.0), f"{label}.opacity"),
        content=_plain_dict(data.get("content", {}), f"{label}.content"),
    )


def _transform_from_dict(raw: Any, label: str) -> ElementTransform:
    data = _mapping(raw, label)
    _keys(
        data,
        required={"x_mm", "y_mm", "width_mm", "height_mm"},
        optional={"rotation_deg"},
        label=label,
    )
    return ElementTransform(
        x_mm=_number(data["x_mm"], f"{label}.x_mm"),
        y_mm=_number(data["y_mm"], f"{label}.y_mm"),
        width_mm=_number(data["width_mm"], f"{label}.width_mm"),
        height_mm=_number(data["height_mm"], f"{label}.height_mm"),
        rotation_deg=_number(data.get("rotation_deg", 0.0), f"{label}.rotation_deg"),
    )


def _export_settings_from_dict(raw: Any) -> ExportSettings:
    data = _mapping(raw, "export_settings")
    _keys(
        data,
        required=set(),
        optional={"dpi", "show_crop_marks", "show_assembly_marks"},
        label="export_settings",
    )
    return ExportSettings(
        dpi=_integer(data.get("dpi", 300), "export_settings.dpi"),
        show_crop_marks=_boolean(
            data.get("show_crop_marks", True), "export_settings.show_crop_marks"
        ),
        show_assembly_marks=_boolean(
            data.get("show_assembly_marks", True), "export_settings.show_assembly_marks"
        ),
    )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CoverValidationError(f"{label} 必須是 JSON 物件。")
    return value


def _plain_dict(value: Any, label: str) -> dict[str, Any]:
    data = dict(_mapping(value, label))
    _validate_json_mapping(data, label)
    return data


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CoverValidationError(f"{label} 必須是 JSON 陣列。")
    return value


def _keys(
    data: Mapping[str, Any], *, required: set[str], optional: set[str], label: str
) -> None:
    missing = sorted(required - data.keys())
    if missing:
        raise CoverValidationError(f"{label} 缺少欄位：{'、'.join(missing)}")
    unknown = sorted(data.keys() - required - optional)
    if unknown:
        raise CoverValidationError(f"{label} 包含未知欄位：{'、'.join(unknown)}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise CoverValidationError(f"{label} 必須是字串。")
    return value


def _integer(value: Any, label: str) -> int:
    if not _is_int(value):
        raise CoverValidationError(f"{label} 必須是整數。")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise CoverValidationError(f"{label} 必須是布林值。")
    return value


def _number(value: Any, label: str) -> float:
    if not _is_finite_number(value):
        raise CoverValidationError(f"{label} 必須是有限數值。")
    return float(value)


def _optional_number(value: Any, label: str) -> float | None:
    return None if value is None else _number(value, label)


def _enum(enum_type: type[Enum], value: Any, label: str) -> Any:
    if not isinstance(value, str):
        raise CoverValidationError(f"{label} 必須是字串。")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise CoverValidationError(f"{label} 無效：{value}") from exc


def _require_non_empty_text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CoverValidationError(f"{label} 不可為空。")


def _require_positive_number(value: Any, label: str) -> None:
    if not _is_finite_number(value) or float(value) <= 0.0:
        raise CoverValidationError(f"{label} 必須大於 0。")


def _require_finite_number(value: Any, label: str) -> None:
    if not _is_finite_number(value):
        raise CoverValidationError(f"{label} 必須是有限數值。")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_json_mapping(value: Any, label: str) -> None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CoverValidationError(f"{label} 必須是 JSON 物件。")
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CoverValidationError(f"{label} 必須只包含 JSON 值。") from exc
