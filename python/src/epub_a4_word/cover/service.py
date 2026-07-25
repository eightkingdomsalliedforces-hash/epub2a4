from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any
from zipfile import BadZipFile, ZipFile

from epub_a4_word.epub import estimate_epub_page_count
from epub_a4_word.pagination import LayoutSettings

from .docx_export import export_docx
from .geometry import calculate_layout
from .metadata import CoverMetadataInspection, inspect_metadata
from .models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    ExportSettings,
    ImageMode,
    Region,
    TrimSize,
)
from .pdf_export import ExportResult, export_pdf
from .project_io import CoverValidationError, dumps_project, loads_project
from .render import render_preview as _render_preview
from .templates import apply_template as _apply_template


_SUPPORTED_TRIMS = (
    (148.0, 210.0),
    (105.0, 148.0),
    (101.6, 152.4),
)
_ALLOWED_SETTINGS = {
    "working_dir",
    "trim_width_mm",
    "trim_height_mm",
    "page_count",
    "paper_caliper_mm",
    "manual_spine_width_mm",
    "bleed_mm",
    "overlap_mm",
    "dpi",
    "show_crop_marks",
    "show_assembly_marks",
    "cover_image_path",
    "image_mode",
}


def _json_object(json_text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise CoverValidationError(f"{label} JSON 無效：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise CoverValidationError(f"{label} JSON 必須是物件。")
    unknown = sorted(set(value) - _ALLOWED_SETTINGS)
    if unknown:
        raise CoverValidationError("不支援的封面設定：" + "、".join(unknown))
    return value


def _required_number(settings: dict[str, Any], key: str) -> float:
    if key not in settings:
        raise CoverValidationError(f"缺少必要設定：{key}")
    value = settings[key]
    if isinstance(value, bool):
        raise CoverValidationError(f"{key} 必須是數字。")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CoverValidationError(f"{key} 必須是數字。") from exc


def _optional_number(settings: dict[str, Any], key: str) -> float | None:
    value = settings.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise CoverValidationError(f"{key} 必須是數字或 null。")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CoverValidationError(f"{key} 必須是數字或 null。") from exc


def _writable_working_dir(value: object) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise CoverValidationError("缺少必要設定：working_dir")
    path = Path(str(value)).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write-probe"
    try:
        probe.write_bytes(b"ok")
    except OSError as exc:
        raise CoverValidationError("工作目錄不可寫入。") from exc
    finally:
        probe.unlink(missing_ok=True)
    return path


def _resolve_page_count(
    inspection: CoverMetadataInspection,
    settings: dict[str, Any],
    source_path: Path,
) -> tuple[int, bool]:
    supplied = settings.get("page_count")
    if supplied is not None:
        if isinstance(supplied, bool):
            raise CoverValidationError("頁數必須大於 0。")
        try:
            count = int(supplied)
        except (TypeError, ValueError) as exc:
            raise CoverValidationError("頁數必須是整數。") from exc
        if count <= 0 or float(supplied) != count:
            raise CoverValidationError("頁數必須大於 0 且為整數。")
        return count, False
    if inspection.fixed_page_count is not None:
        return inspection.fixed_page_count, False
    if source_path.suffix.lower() == ".epub":
        return (
            estimate_epub_page_count(
                source_path,
                LayoutSettings(imposition_mode="single_a5"),
            ),
            True,
        )
    raise CoverValidationError("無法自動取得頁數，請輸入並確認正文頁數。")


def _safe_asset_name(name: str) -> str:
    filename = PurePosixPath(name.replace("\\", "/")).name
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", filename).strip("._")
    return safe or "cover-image"


def _write_asset_bytes(data: bytes, source_name: str, assets_dir: Path) -> Path:
    digest = hashlib.sha256(data).hexdigest()[:16]
    destination = assets_dir / f"{digest}-{_safe_asset_name(source_name)}"
    if not destination.exists():
        destination.write_bytes(data)
    return destination.resolve()


def _copy_asset(source: Path, assets_dir: Path) -> Path:
    if not source.is_file():
        raise CoverValidationError(f"找不到封面圖片：{source}")
    data = source.read_bytes()
    return _write_asset_bytes(data, source.name, assets_dir)


def _extract_epub_cover(
    source: Path,
    inspection: CoverMetadataInspection,
    assets_dir: Path,
) -> Path | None:
    selected = next(
        (
            item
            for item in inspection.metadata.embedded_images
            if item.get("role") == "cover" and isinstance(item.get("href"), str)
        ),
        None,
    )
    if selected is None:
        return None
    href = str(selected["href"])
    try:
        with ZipFile(source) as package:
            data = package.read(href)
    except (BadZipFile, KeyError) as exc:
        raise CoverValidationError(f"無法提取 EPUB 封面圖片：{href}") from exc
    return _write_asset_bytes(data, href, assets_dir)


def _cover_asset(
    source: Path,
    inspection: CoverMetadataInspection,
    settings: dict[str, Any],
    assets_dir: Path,
) -> Path | None:
    explicit = settings.get("cover_image_path")
    if explicit is not None:
        return _copy_asset(Path(str(explicit)).expanduser().resolve(), assets_dir)
    if inspection.source_type == "epub":
        return _extract_epub_cover(source, inspection, assets_dir)
    return None


def _trim_size(settings: dict[str, Any]) -> TrimSize:
    width = _required_number(settings, "trim_width_mm")
    height = _required_number(settings, "trim_height_mm")
    if not any(abs(width - item[0]) < 1e-6 and abs(height - item[1]) < 1e-6 for item in _SUPPORTED_TRIMS):
        raise CoverValidationError("裁切尺寸只支援 A5、A6 或 4×6 英吋。")
    return TrimSize(width, height)


def _result_dict(result: ExportResult) -> dict[str, Any]:
    return {
        "path": str(result.path),
        "page_count": result.page_count,
        "mode": result.mode,
        "dpi": result.dpi,
        "warnings": list(result.warnings),
    }


def inspect_source(source_path: str) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    inspection = inspect_metadata(source)
    return {
        "source_path": str(source),
        "source_type": inspection.source_type,
        "metadata": asdict(inspection.metadata),
        "fixed_page_count": inspection.fixed_page_count,
        "warnings": list(inspection.warnings),
    }


def new_project(source_path: str, settings_json: str) -> str:
    source = Path(source_path).expanduser().resolve()
    inspection = inspect_metadata(source)
    settings = _json_object(settings_json, "封面設定")
    working_dir = _writable_working_dir(settings.get("working_dir"))
    assets_dir = working_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    page_count, estimated = _resolve_page_count(inspection, settings, source)
    metadata = replace(inspection.metadata, page_count_is_estimate=estimated)
    image_mode_value = settings.get("image_mode", ImageMode.FRONT_ONLY.value)
    try:
        image_mode = ImageMode(str(image_mode_value))
    except ValueError as exc:
        raise CoverValidationError("image_mode 無效。") from exc

    project = CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type=inspection.source_type,
        metadata=metadata,
        trim_size=_trim_size(settings),
        page_count=page_count,
        paper_caliper_mm=_required_number(settings, "paper_caliper_mm"),
        manual_spine_width_mm=_optional_number(settings, "manual_spine_width_mm"),
        bleed_mm=_required_number(settings, "bleed_mm"),
        overlap_mm=_required_number(settings, "overlap_mm"),
        image_mode=image_mode,
        working_dir=str(working_dir),
        background={"warnings": list(inspection.warnings)} if inspection.warnings else {},
        export_settings=ExportSettings(
            dpi=int(settings.get("dpi", 300)),
            show_crop_marks=bool(settings.get("show_crop_marks", True)),
            show_assembly_marks=bool(settings.get("show_assembly_marks", True)),
        ),
    )
    asset = _cover_asset(source, inspection, settings, assets_dir)
    if asset is not None:
        layout = calculate_layout(project)
        target = layout.bleed_rect if image_mode is ImageMode.FULL_SPREAD else layout.front_rect
        image = CoverElement(
            id="source-cover-image",
            kind=ElementKind.IMAGE,
            region=Region.SPREAD if image_mode is ImageMode.FULL_SPREAD else Region.FRONT,
            transform=ElementTransform(
                target.x_mm,
                target.y_mm,
                target.width_mm,
                target.height_mm,
            ),
            z_index=-15,
            content={"path": str(asset), "fit": "cover"},
        )
        project = replace(project, elements=(image,))
    return dumps_project(project)


def extract_embedded_asset(project_json: str, asset_id: str) -> dict[str, Any]:
    """Extract one manifest-declared EPUB image into the project assets folder.

    The caller supplies the stable manifest item id returned by metadata
    inspection. The archive member path is never accepted directly from UI.
    """
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise CoverValidationError("內嵌圖片 ID 不可為空。")
    project = loads_project(project_json)
    if project.source_type != "epub":
        raise CoverValidationError("只有 EPUB 專案包含可提取的內嵌圖片。")
    source = Path(project.source_file).expanduser().resolve()
    if not source.is_file():
        raise CoverValidationError("找不到 EPUB 來源文件。")
    selected = next(
        (
            item
            for item in project.metadata.embedded_images
            if item.get("id") == asset_id and isinstance(item.get("href"), str)
        ),
        None,
    )
    if selected is None:
        raise CoverValidationError(f"找不到 EPUB 內嵌圖片：{asset_id}")
    href = str(selected["href"])
    try:
        with ZipFile(source) as package:
            data = package.read(href)
    except (BadZipFile, KeyError) as exc:
        raise CoverValidationError(f"無法提取 EPUB 內嵌圖片：{href}") from exc
    working_dir = _writable_working_dir(project.working_dir)
    assets_dir = working_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    path = _write_asset_bytes(data, href, assets_dir)
    return {
        "asset_id": asset_id,
        "path": str(path),
        "media_type": str(selected.get("media_type", "application/octet-stream")),
        "role": str(selected.get("role", "image")),
    }


def apply_template(project_json: str, template_id: str) -> str:
    return dumps_project(_apply_template(loads_project(project_json), template_id))


def render_preview(project_json: str, output_png: str, max_px: int = 1600) -> dict[str, Any]:
    result = _render_preview(loads_project(project_json), Path(output_png), max_px=max_px)
    return {
        "path": str(result.path),
        "width_px": result.width_px,
        "height_px": result.height_px,
        "warnings": list(result.warnings),
    }


def export_cover(
    project_json: str,
    pdf_path: str,
    docx_path: str,
    dpi: int = 300,
) -> dict[str, Any]:
    project = loads_project(project_json)
    pdf_result = export_pdf(project, Path(pdf_path), dpi=dpi)
    docx_result = export_docx(project, Path(docx_path))
    return {
        "pdf": _result_dict(pdf_result),
        "docx": _result_dict(docx_result),
        "dpi": dpi,
    }
