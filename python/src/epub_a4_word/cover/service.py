from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from zipfile import BadZipFile, ZipFile

from epub_a4_word.epub import estimate_epub_page_count
from epub_a4_word.pagination import LayoutSettings

from .docx_export import export_docx
from .export_plan import build_export_plan
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
from .pdf_export import ExportResult, export_original_pdf, export_pdf
from .project_io import CoverValidationError, dumps_project, loads_project
from .render import render_preview as _render_preview
from .templates import apply_template as _apply_template

_SUPPORTED_TRIMS = (
    (148.0, 210.0),
    (128.0, 182.0),
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
    "translator",
    "confirmed_back_cover_asset_id",
}


def _layout_mode_for_trim(
    trim_width_mm: float | None, trim_height_mm: float | None
) -> str:
    if trim_width_mm is None or trim_height_mm is None:
        return "single_a5"
    target = (float(trim_width_mm), float(trim_height_mm))
    if all(abs(a - b) < 1e-6 for a, b in zip(target, (128.0, 182.0))):
        return "b6_on_a5"
    if all(abs(a - b) < 1e-6 for a, b in zip(target, (101.6, 152.4))):
        return "single_4x6"
    if all(abs(a - b) < 1e-6 for a, b in zip(target, (105.0, 148.0))):
        return "signature16"
    return "single_a5"


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
                LayoutSettings(
                    imposition_mode=_layout_mode_for_trim(
                        settings.get("trim_width_mm"),
                        settings.get("trim_height_mm"),
                    )
                ),
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
    return _write_asset_bytes(source.read_bytes(), source.name, assets_dir)


def _extract_epub_cover_assets(
    source: Path,
    inspection: CoverMetadataInspection,
    assets_dir: Path,
    *,
    confirmed_back_cover_asset_id: str = "",
) -> tuple[Path | None, Path | None]:
    front = next(
        (
            item
            for item in inspection.metadata.embedded_images
            if item.get("role") in {"cover", "front_cover"} and isinstance(item.get("href"), str)
        ),
        None,
    )
    confirmed_id = confirmed_back_cover_asset_id.strip()
    back = next(
        (
            item
            for item in inspection.metadata.embedded_images
            if (
                item.get("role") == "back_cover"
                or (
                    confirmed_id
                    and item.get("role") == "back_cover_candidate"
                    and item.get("id") == confirmed_id
                )
            )
            and isinstance(item.get("href"), str)
        ),
        None,
    )
    if front is None and back is None:
        return None, None

    extracted: dict[str, Path] = {}
    try:
        with ZipFile(source) as package:
            for selected in (front, back):
                if selected is None:
                    continue
                href = str(selected["href"])
                try:
                    data = package.read(href)
                except KeyError as exc:
                    raise CoverValidationError(f"無法提取 EPUB 封面圖片：{href}") from exc
                extracted[href] = _write_asset_bytes(data, href, assets_dir)
    except BadZipFile as exc:
        raise CoverValidationError("無法提取 EPUB 封面圖片：EPUB 壓縮檔無效。") from exc

    front_path = extracted.get(str(front["href"])) if front is not None else None
    back_path = extracted.get(str(back["href"])) if back is not None else None
    return front_path, back_path


def _cover_assets(
    source: Path,
    inspection: CoverMetadataInspection,
    settings: dict[str, Any],
    assets_dir: Path,
) -> tuple[Path | None, Path | None]:
    explicit = settings.get("cover_image_path")
    if explicit is not None:
        return _copy_asset(Path(str(explicit)).expanduser().resolve(), assets_dir), None
    if inspection.source_type == "epub":
        return _extract_epub_cover_assets(
            source,
            inspection,
            assets_dir,
            confirmed_back_cover_asset_id=str(
                settings.get("confirmed_back_cover_asset_id", "")
            ),
        )
    return None, None


def _trim_size(settings: dict[str, Any]) -> TrimSize:
    width = _required_number(settings, "trim_width_mm")
    height = _required_number(settings, "trim_height_mm")
    if not any(
        abs(width - item[0]) < 1e-6 and abs(height - item[1]) < 1e-6
        for item in _SUPPORTED_TRIMS
    ):
        raise CoverValidationError("裁切尺寸只支援 A5、B6、A6 或 4×6 英吋。")
    return TrimSize(width, height)


def _result_dict(result: ExportResult) -> dict[str, Any]:
    return {
        "path": str(result.path),
        "page_count": result.page_count,
        "mode": result.mode,
        "dpi": result.dpi,
        "warnings": list(result.warnings),
    }


def inspect_source(
    source_path: str,
    trim_width_mm: float | None = None,
    trim_height_mm: float | None = None,
) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    inspection = inspect_metadata(source)
    page_count = inspection.fixed_page_count
    estimated = False
    if page_count is None and inspection.source_type == "epub":
        page_count = estimate_epub_page_count(
            source,
            LayoutSettings(
                imposition_mode=_layout_mode_for_trim(trim_width_mm, trim_height_mm)
            ),
        )
        estimated = True
    metadata = replace(inspection.metadata, page_count_is_estimate=estimated)
    return {
        "source_path": str(source),
        "source_type": inspection.source_type,
        "metadata": asdict(metadata),
        "fixed_page_count": inspection.fixed_page_count,
        "page_count": page_count,
        "page_count_estimated": estimated,
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
    translator = str(settings.get("translator", "")).strip()
    metadata = replace(
        inspection.metadata,
        translator=translator or inspection.metadata.translator,
        page_count_is_estimate=estimated,
    )
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
    front_asset, back_asset = _cover_assets(source, inspection, settings, assets_dir)
    if front_asset is not None:
        layout = calculate_layout(project)
        if image_mode is ImageMode.FULL_SPREAD:
            target = layout.bleed_rect
            elements = (
                CoverElement(
                    id="source-cover-image",
                    kind=ElementKind.IMAGE,
                    region=Region.SPREAD,
                    transform=ElementTransform(
                        target.x_mm,
                        target.y_mm,
                        target.width_mm,
                        target.height_mm,
                    ),
                    z_index=-15,
                    content={"path": str(front_asset), "fit": "cover"},
                ),
            )
        else:
            front_target = layout.front_rect
            elements_list = [
                CoverElement(
                    id="source-cover-image",
                    kind=ElementKind.IMAGE,
                    region=Region.FRONT,
                    transform=ElementTransform(
                        front_target.x_mm,
                        front_target.y_mm,
                        front_target.width_mm,
                        front_target.height_mm,
                    ),
                    z_index=-15,
                    content={"path": str(front_asset), "fit": "cover"},
                )
            ]
            if back_asset is not None:
                back_target = layout.back_rect
                elements_list.append(
                    CoverElement(
                        id="source-back-cover-image",
                        kind=ElementKind.IMAGE,
                        region=Region.BACK,
                        transform=ElementTransform(
                            back_target.x_mm,
                            back_target.y_mm,
                            back_target.width_mm,
                            back_target.height_mm,
                        ),
                        z_index=-15,
                        content={"path": str(back_asset), "fit": "cover"},
                    )
                )
                image_mode = ImageMode.SEPARATE_COVERS
            elements = tuple(elements_list)
        project = replace(project, image_mode=image_mode, elements=elements)
    return dumps_project(project)


def extract_embedded_asset(project_json: str, asset_id: str) -> dict[str, Any]:
    """Extract one manifest-declared EPUB image into the project assets folder."""
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


def export_cover_bundle(
    project_json: str,
    original_pdf_path: str,
    print_pdf_path: str,
    print_docx_path: str,
    dpi: int = 300,
) -> dict[str, Any]:
    project = loads_project(project_json)
    export_plan = build_export_plan(project)
    original_result = export_original_pdf(project, Path(original_pdf_path), dpi=dpi)
    print_pdf_result = export_pdf(project, Path(print_pdf_path), dpi=dpi)
    print_docx_result = export_docx(project, Path(print_docx_path))
    return {
        "original_pdf": _result_dict(original_result),
        "print_pdf": _result_dict(print_pdf_result),
        "print_docx": _result_dict(print_docx_result),
        "print_plan": {
            "mode": export_plan.print_plan.mode,
            "page_count": len(export_plan.print_plan.pages),
            "overlap_mm": export_plan.overlap_mm,
            "back_cover_blank": export_plan.back_cover_blank,
        },
        "dpi": dpi,
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


def search_covers(request_json: str) -> str:
    """JSON boundary used by desktop/Android callers without retaining credentials."""
    from .search import (
        GeneralCoverSearch,
        GoogleBooksProvider,
        GoogleCustomSearchProvider,
        JsonHttpClient,
        OpenLibraryProvider,
        ProviderCredential,
        PublicBookSearch,
        SearchKind,
    )
    from .search.models import CoverSearchRequest

    try:
        raw = json.loads(request_json)
    except json.JSONDecodeError as exc:
        raise CoverValidationError(f"搜尋 JSON 無效：{exc.msg}") from exc
    if not isinstance(raw, dict):
        raise CoverValidationError("搜尋 JSON 必須是物件。")
    mode = str(raw.get("mode", "public_books"))
    request = CoverSearchRequest(
        kind=SearchKind(str(raw.get("kind", "front"))),
        query=str(raw.get("query", "")),
        isbn=str(raw.get("isbn", "")),
        title=str(raw.get("title", "")),
        author=str(raw.get("author", "")),
        locale=str(raw.get("locale", "zh-TW")),
        max_results=int(raw.get("max_results", 20)),
        safe_search=bool(raw.get("safe_search", True)),
    )
    http = JsonHttpClient()
    if mode == "public_books":
        response = PublicBookSearch(
            (GoogleBooksProvider(http), OpenLibraryProvider(http))
        ).search(request)
    elif mode == "general_images":
        credential_raw = raw.get("credential")
        credential_raw = credential_raw if isinstance(credential_raw, dict) else {}
        credential = ProviderCredential(
            str(credential_raw.get("api_key", "")),
            str(credential_raw.get("search_engine_id", "")),
        )
        response = GeneralCoverSearch(GoogleCustomSearchProvider(http)).search_all(
            title=request.title,
            author=request.author,
            isbn=request.isbn,
            locale=request.locale,
            credential=credential,
            max_results=min(request.max_results, 10),
        )
    else:
        raise CoverValidationError("搜尋模式無效。")
    return json.dumps(response.to_dict(), ensure_ascii=False)


def download_search_candidate(
    candidate_json: str,
    destination_path: str,
) -> dict[str, object]:
    from .search import JsonHttpClient, SearchCandidate, download_candidate

    try:
        raw = json.loads(candidate_json)
    except json.JSONDecodeError as exc:
        raise CoverValidationError(f"候選圖片 JSON 無效：{exc.msg}") from exc
    if not isinstance(raw, dict):
        raise CoverValidationError("候選圖片 JSON 必須是物件。")
    result = download_candidate(
        SearchCandidate.from_dict(raw),
        Path(destination_path),
        JsonHttpClient(),
    )
    return {
        "path": str(result.path),
        "content_type": result.content_type,
        "byte_count": result.byte_count,
        "width": result.width,
        "height": result.height,
        "sha256": result.sha256,
    }
