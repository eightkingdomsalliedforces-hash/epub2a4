from __future__ import annotations

import io
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urldefrag
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError
from lxml import etree
from pypdf import PdfReader

from .models import CoverMetadata


@dataclass(frozen=True)
class CoverMetadataInspection:
    source_type: str
    metadata: CoverMetadata
    fixed_page_count: int | None
    warnings: tuple[str, ...] = ()


def inspect_metadata(source_path: Path | str) -> CoverMetadataInspection:
    source = Path(source_path)
    if not source.is_file():
        raise ValueError("找不到來源文件。")
    readers: dict[str, Callable[[Path], CoverMetadataInspection]] = {
        ".epub": _inspect_epub,
        ".docx": _inspect_docx,
        ".pdf": _inspect_pdf,
    }
    try:
        reader = readers[source.suffix.lower()]
    except KeyError as exc:
        raise ValueError("封面工具只支援 EPUB、DOCX 或 PDF。") from exc
    return reader(source)


def _inspect_epub(source: Path) -> CoverMetadataInspection:
    warnings: list[str] = []
    try:
        with ZipFile(source) as archive:
            names = set(archive.namelist())
            container_root = _parse_xml(archive.read("META-INF/container.xml"), "EPUB container.xml")
            rootfile = next(_iter_local(container_root, "rootfile"), None)
            if rootfile is None or not rootfile.get("full-path"):
                raise ValueError("EPUB container.xml 沒有 OPF 路徑。")
            opf_path = str(rootfile.get("full-path"))
            if opf_path not in names:
                raise ValueError(f"EPUB 缺少套件檔：{opf_path}")
            package = _parse_xml(archive.read(opf_path), "EPUB OPF")

            metadata_node = next(_iter_local(package, "metadata"), None)
            title = _first_local_text(metadata_node, "title")
            author = _first_local_text(metadata_node, "creator")
            description = _first_local_text(metadata_node, "description")
            publisher = _first_local_text(metadata_node, "publisher")
            language = _first_local_text(metadata_node, "language")
            isbn = _epub_identifier(package, metadata_node)

            items: list[dict[str, str]] = []
            for node in _iter_local(package, "item"):
                item_id = node.get("id", "")
                href = node.get("href", "")
                if not item_id or not href:
                    continue
                resolved = _archive_path(opf_path, href)
                media_type = node.get("media-type", "")
                properties = node.get("properties", "")
                if media_type.startswith("image/") or _looks_like_image(resolved):
                    items.append(
                        {
                            "id": item_id,
                            "href": resolved,
                            "media_type": media_type or _media_type_from_name(resolved),
                            "properties": properties,
                        }
                    )

            cover_id = next(
                (
                    item["id"]
                    for item in items
                    if "cover-image" in item["properties"].split()
                ),
                "",
            )
            if not cover_id and metadata_node is not None:
                for meta in _iter_local(metadata_node, "meta"):
                    if (meta.get("name") or "").lower() == "cover":
                        cover_id = meta.get("content", "")
                        if cover_id:
                            break
            if not cover_id and items:
                cover_id = items[0]["id"]

            ordered_items = sorted(items, key=lambda item: item["id"] != cover_id)
            embedded_images: list[dict[str, Any]] = []
            for item in ordered_items:
                width_px: int | None = None
                height_px: int | None = None
                href = item["href"]
                if href not in names:
                    warnings.append(f"找不到內嵌圖片：{href}")
                else:
                    width_px, height_px = _image_dimensions(archive.read(href), href, warnings)
                embedded_images.append(
                    {
                        "id": item["id"],
                        "href": href,
                        "media_type": item["media_type"],
                        "role": "cover" if item["id"] == cover_id else "image",
                        "width_px": width_px,
                        "height_px": height_px,
                    }
                )
    except KeyError as exc:
        raise ValueError(f"EPUB 缺少必要檔案：{exc.args[0]}") from exc
    except BadZipFile as exc:
        raise ValueError("檔案不是有效的 EPUB/ZIP。") from exc

    return CoverMetadataInspection(
        source_type="epub",
        metadata=CoverMetadata(
            title=title,
            author=author,
            description=description,
            isbn=isbn,
            publisher=publisher,
            language=language,
            embedded_images=tuple(embedded_images),
        ),
        fixed_page_count=None,
        warnings=tuple(warnings),
    )


def _inspect_docx(source: Path) -> CoverMetadataInspection:
    warnings: list[str] = []
    try:
        with ZipFile(source) as archive:
            try:
                core = _parse_xml(archive.read("docProps/core.xml"), "DOCX core properties")
            except KeyError:
                core = None
                warnings.append("DOCX 缺少核心中繼資料。")

            page_count: int | None = None
            try:
                app = _parse_xml(archive.read("docProps/app.xml"), "DOCX app properties")
                pages_text = _first_local_text(app, "Pages")
                if pages_text:
                    try:
                        parsed_pages = int(pages_text)
                    except ValueError:
                        warnings.append("DOCX 頁數欄位無效。")
                    else:
                        if parsed_pages > 0:
                            page_count = parsed_pages
                        else:
                            warnings.append("DOCX 頁數欄位必須大於 0。")
                else:
                    warnings.append("DOCX 沒有可用的頁數中繼資料。")
            except KeyError:
                warnings.append("DOCX 缺少頁數中繼資料。")
    except BadZipFile as exc:
        raise ValueError("檔案不是有效的 DOCX。") from exc

    return CoverMetadataInspection(
        source_type="docx",
        metadata=CoverMetadata(
            title=_first_local_text(core, "title"),
            author=_first_local_text(core, "creator"),
            description=_first_local_text(core, "description"),
            isbn=_normalize_identifier(_first_local_text(core, "identifier")),
            language=_first_local_text(core, "language"),
        ),
        fixed_page_count=page_count,
        warnings=tuple(warnings),
    )


def _inspect_pdf(source: Path) -> CoverMetadataInspection:
    try:
        reader = PdfReader(str(source))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:  # pypdf raises several backend-specific errors.
                raise ValueError("無法讀取加密 PDF。") from exc
            if not unlocked:
                raise ValueError("無法讀取加密 PDF。")
        page_count = len(reader.pages)
        raw_metadata = reader.metadata or {}
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("無法讀取 PDF。") from exc

    metadata = {_normalize_pdf_key(key): _metadata_text(value) for key, value in raw_metadata.items()}
    return CoverMetadataInspection(
        source_type="pdf",
        metadata=CoverMetadata(
            title=metadata.get("Title", ""),
            author=metadata.get("Author", ""),
            description=metadata.get("Subject", ""),
            isbn=_normalize_identifier(metadata.get("Keywords", "")),
            publisher=metadata.get("Publisher", metadata.get("Producer", "")),
            language=metadata.get("Language", ""),
        ),
        fixed_page_count=page_count,
    )


def _parse_xml(data: bytes, label: str) -> etree._Element:
    try:
        return etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"{label} XML 無效。") from exc


def _iter_local(root: etree._Element | None, local_name: str):
    if root is None:
        return iter(())
    return (node for node in root.iter() if etree.QName(node).localname == local_name)


def _first_local_text(root: etree._Element | None, local_name: str) -> str:
    node = next(_iter_local(root, local_name), None)
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _epub_identifier(
    package: etree._Element, metadata_node: etree._Element | None
) -> str:
    identifiers = list(_iter_local(metadata_node, "identifier"))
    unique_id = package.get("unique-identifier", "")
    if unique_id:
        for node in identifiers:
            if node.get("id") == unique_id:
                return _normalize_identifier(_first_node_text(node))
    for node in identifiers:
        value = _normalize_identifier(_first_node_text(node))
        if re.fullmatch(r"(?:97[89])?\d{9}[\dXx]", value):
            return value
    return _normalize_identifier(_first_node_text(identifiers[0])) if identifiers else ""


def _first_node_text(node: etree._Element) -> str:
    return " ".join("".join(node.itertext()).split())


def _normalize_identifier(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^urn:isbn:", "", value, flags=re.IGNORECASE)
    compact = re.sub(r"[\s-]", "", value)
    return compact if re.fullmatch(r"(?:97[89])?\d{9}[\dXx]", compact) else value


def _archive_path(base_file: str, href: str) -> str:
    decoded, _fragment = urldefrag(unquote(href or ""))
    decoded = decoded.replace("\\", "/")
    base = posixpath.dirname(base_file)
    return posixpath.normpath(posixpath.join(base, decoded)).lstrip("/")


def _looks_like_image(path: str) -> bool:
    return Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}


def _media_type_from_name(path: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".svg": "image/svg+xml",
    }.get(Path(path).suffix.lower(), "application/octet-stream")


def _image_dimensions(
    data: bytes, href: str, warnings: list[str]
) -> tuple[int | None, int | None]:
    if Path(href).suffix.lower() == ".svg":
        return None, None
    try:
        with Image.open(io.BytesIO(data)) as image:
            return int(image.width), int(image.height)
    except (UnidentifiedImageError, OSError, ValueError):
        warnings.append(f"無法讀取內嵌圖片尺寸：{href}")
        return None, None


def _normalize_pdf_key(key: Any) -> str:
    return str(key).lstrip("/")


def _metadata_text(value: Any) -> str:
    return "" if value is None else str(value)
