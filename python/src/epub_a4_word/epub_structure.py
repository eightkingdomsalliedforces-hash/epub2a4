from __future__ import annotations

import io
import posixpath
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import unquote, urldefrag
from zipfile import BadZipFile, ZipFile

from lxml import etree
from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError


class CoverConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    NONE = "none"


@dataclass(frozen=True)
class EpubManifestItem:
    id: str
    href: str
    media_type: str
    properties: tuple[str, ...] = ()


@dataclass(frozen=True)
class EpubCoverDetection:
    front_resource: str | None
    front_page: str | None
    front_pages: tuple[str, ...]
    back_resource: str | None
    back_page: str | None
    back_confidence: CoverConfidence
    back_reasons: tuple[str, ...]


@dataclass(frozen=True)
class EpubStructure:
    opf_path: str
    manifest: dict[str, EpubManifestItem]
    spine_ids: tuple[str, ...]
    spine_documents: tuple[str, ...]
    detection: EpubCoverDetection


_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
_FRONT_WORDS = ("cover", "front", "front-cover", "frontcover", "表紙", "封面")
_BACK_WORDS = ("back-cover", "backcover", "rear-cover", "rearcover", "rear", "封底", "裏表紙")


def _archive_path(base_file: str, href: str) -> str:
    decoded, _fragment = urldefrag(unquote(href or ""))
    decoded = decoded.replace("\\", "/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_file), decoded)).lstrip("/")


def _iter_local(root: etree._Element | None, local_name: str):
    if root is None:
        return iter(())
    return (node for node in root.iter() if etree.QName(node).localname == local_name)


def _local_attr(node: etree._Element, local_name: str) -> str:
    for key, value in node.attrib.items():
        if etree.QName(key).localname == local_name:
            return value
    return ""


def _parse_xml(data: bytes, label: str) -> etree._Element:
    try:
        return etree.fromstring(data, parser=etree.XMLParser(recover=False, resolve_entities=False))
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"{label} XML 無效。") from exc


def _parse_xhtml(data: bytes) -> etree._Element | None:
    try:
        return etree.fromstring(data, parser=etree.XMLParser(recover=True, resolve_entities=False))
    except etree.XMLSyntaxError:
        return None


def _is_image(item: EpubManifestItem | None) -> bool:
    if item is None:
        return False
    return item.media_type.startswith("image/") or Path(item.href).suffix.lower() in _IMAGE_SUFFIXES


def _is_document(item: EpubManifestItem | None) -> bool:
    if item is None:
        return False
    return item.media_type in {"application/xhtml+xml", "text/html"} or Path(item.href).suffix.lower() in {
        ".xhtml",
        ".html",
        ".htm",
    }


def _semantic_text(*values: str) -> str:
    return " ".join(value for value in values if value).lower().replace("_", "-")


def _has_back_semantics(value: str) -> bool:
    normalized = _semantic_text(value)
    return any(word in normalized for word in _BACK_WORDS)


def _has_front_semantics(value: str) -> bool:
    normalized = _semantic_text(value)
    return not _has_back_semantics(normalized) and any(word in normalized for word in _FRONT_WORDS)


def _pure_image_page(
    archive: ZipFile,
    document_path: str,
    names: set[str],
) -> tuple[str, str] | None:
    if document_path not in names:
        return None
    root = _parse_xhtml(archive.read(document_path))
    if root is None:
        return None
    body = next(_iter_local(root, "body"), root)
    text = " ".join("".join(body.itertext()).split())
    if text:
        return None
    image_nodes = [node for node in body.iter() if etree.QName(node).localname in {"img", "image"}]
    if len(image_nodes) != 1:
        return None
    image = image_nodes[0]
    href = image.get("src") or image.get("href") or _local_attr(image, "href")
    if not href:
        return None
    resource = _archive_path(document_path, href)
    if resource not in names:
        return None
    semantics = _semantic_text(
        document_path,
        image.get("id", ""),
        image.get("class", ""),
        image.get("title", ""),
        image.get("alt", ""),
        resource,
    )
    return resource, semantics


def _image_dimensions(archive: ZipFile, path: str | None, names: set[str]) -> tuple[int, int] | None:
    if not path or path not in names or Path(path).suffix.lower() == ".svg":
        return None
    try:
        with Image.open(io.BytesIO(archive.read(path))) as image:
            return int(image.width), int(image.height)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _similar_dimensions(first: tuple[int, int] | None, second: tuple[int, int] | None) -> bool:
    if first is None or second is None:
        return False
    fw, fh = first
    sw, sh = second
    if min(fw, fh, sw, sh) <= 0:
        return False
    first_ratio = fw / fh
    second_ratio = sw / sh
    ratio_delta = abs(first_ratio - second_ratio) / max(first_ratio, second_ratio)
    width_delta = abs(fw - sw) / max(fw, sw)
    height_delta = abs(fh - sh) / max(fh, sh)
    return ratio_delta <= 0.12 and width_delta <= 0.35 and height_delta <= 0.35


def _visually_similar_images(
    archive: ZipFile,
    first: str | None,
    second: str | None,
    names: set[str],
) -> bool:
    if (
        not first
        or not second
        or first not in names
        or second not in names
        or not _similar_dimensions(
            _image_dimensions(archive, first, names),
            _image_dimensions(archive, second, names),
        )
    ):
        return False
    try:
        with Image.open(io.BytesIO(archive.read(first))) as first_image:
            normalized_first = first_image.convert("RGB").resize((32, 32))
        with Image.open(io.BytesIO(archive.read(second))) as second_image:
            normalized_second = second_image.convert("RGB").resize((32, 32))
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    difference = ImageChops.difference(normalized_first, normalized_second)
    return sum(ImageStat.Stat(difference).mean) / 3.0 <= 6.0


def _has_barcode_pattern(
    archive: ZipFile,
    path: str | None,
    names: set[str],
) -> bool:
    if not path or path not in names or Path(path).suffix.lower() == ".svg":
        return False
    try:
        with Image.open(io.BytesIO(archive.read(path))) as source:
            grayscale = source.convert("L")
            height = max(1, round(grayscale.height * 512 / grayscale.width))
            image = grayscale.resize((512, height))
    except (UnidentifiedImageError, OSError, ValueError, ZeroDivisionError):
        return False

    barcode_rows = 0
    for y in range(max(1, round(image.height * 0.45))):
        dark = [pixel < 100 for pixel in image.crop((0, y, 512, y + 1)).getdata()]
        dark_fraction = sum(dark) / len(dark)
        transitions = sum(first != second for first, second in zip(dark, dark[1:]))
        if 0.03 <= dark_fraction <= 0.65 and transitions >= 60:
            barcode_rows += 1
            if barcode_rows >= 6:
                return True
    return False


def _resolve_reference(
    opf_path: str,
    href: str,
    manifest_by_href: dict[str, EpubManifestItem],
    page_images: dict[str, tuple[str, str]],
) -> tuple[str | None, str | None]:
    path = _archive_path(opf_path, href)
    item = manifest_by_href.get(path)
    if _is_image(item) or Path(path).suffix.lower() in _IMAGE_SUFFIXES:
        return path, None
    pure = page_images.get(path)
    if pure is not None:
        return pure[0], path
    return None, path if item and _is_document(item) else None


def inspect_epub_structure(path: Path | str) -> EpubStructure:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"找不到 EPUB：{source}")

    try:
        archive = ZipFile(source)
    except BadZipFile as exc:
        raise ValueError("檔案不是有效的 EPUB/ZIP。") from exc

    with archive:
        names = set(archive.namelist())
        try:
            container = _parse_xml(archive.read("META-INF/container.xml"), "EPUB container.xml")
        except KeyError as exc:
            raise ValueError("EPUB 缺少 META-INF/container.xml。") from exc
        rootfile = next(_iter_local(container, "rootfile"), None)
        if rootfile is None or not rootfile.get("full-path"):
            raise ValueError("EPUB container.xml 沒有 OPF 路徑。")
        opf_path = str(rootfile.get("full-path"))
        if opf_path not in names:
            raise ValueError(f"EPUB 缺少套件檔：{opf_path}")
        package = _parse_xml(archive.read(opf_path), "EPUB OPF")

        manifest: dict[str, EpubManifestItem] = {}
        for node in _iter_local(package, "item"):
            item_id = node.get("id", "")
            href = node.get("href", "")
            if not item_id or not href:
                continue
            manifest[item_id] = EpubManifestItem(
                id=item_id,
                href=_archive_path(opf_path, href),
                media_type=node.get("media-type", ""),
                properties=tuple((node.get("properties") or "").split()),
            )
        manifest_by_href = {item.href: item for item in manifest.values()}

        spine = next(_iter_local(package, "spine"), None)
        spine_ids = tuple(
            node.get("idref", "")
            for node in _iter_local(spine, "itemref")
            if node.get("idref")
        )
        spine_documents = tuple(
            manifest[item_id].href
            for item_id in spine_ids
            if item_id in manifest and _is_document(manifest[item_id])
        )

        page_images: dict[str, tuple[str, str]] = {}
        resource_pages: dict[str, list[str]] = {}
        for document_path in spine_documents:
            pure = _pure_image_page(archive, document_path, names)
            if pure is None:
                continue
            page_images[document_path] = pure
            resource_pages.setdefault(pure[0], []).append(document_path)

        front_resource: str | None = None
        front_page: str | None = None

        cover_image_item = next(
            (item for item in manifest.values() if "cover-image" in item.properties and _is_image(item)),
            None,
        )
        if cover_image_item is not None:
            front_resource = cover_image_item.href

        metadata = next(_iter_local(package, "metadata"), None)
        if front_resource is None and metadata is not None:
            for meta in _iter_local(metadata, "meta"):
                if (meta.get("name") or "").lower() == "cover":
                    item = manifest.get(meta.get("content", ""))
                    if _is_image(item):
                        front_resource = item.href
                        break

        explicit_references: list[tuple[str, str, str]] = []
        guide = next(_iter_local(package, "guide"), None)
        for reference in _iter_local(guide, "reference"):
            explicit_references.append(
                ("guide", _semantic_text(reference.get("type", ""), reference.get("title", "")), reference.get("href", ""))
            )

        nav_items = [item for item in manifest.values() if "nav" in item.properties and item.href in names]
        for nav_item in nav_items:
            nav_root = _parse_xhtml(archive.read(nav_item.href))
            if nav_root is None:
                continue
            for nav in _iter_local(nav_root, "nav"):
                nav_type = _local_attr(nav, "type")
                if "landmarks" not in nav_type.lower():
                    continue
                for anchor in _iter_local(nav, "a"):
                    explicit_references.append(
                        (
                            "landmarks",
                            _semantic_text(_local_attr(anchor, "type"), " ".join(anchor.itertext())),
                            _archive_path(nav_item.href, anchor.get("href", "")),
                        )
                    )

        if front_resource is None:
            for source_name, semantics, href in explicit_references:
                if not _has_front_semantics(semantics):
                    continue
                if source_name == "landmarks":
                    resource, page = _resolve_reference("", href, manifest_by_href, page_images)
                else:
                    resource, page = _resolve_reference(opf_path, href, manifest_by_href, page_images)
                if resource:
                    front_resource, front_page = resource, page
                    break

        if front_resource is None and spine_documents:
            first_page = spine_documents[0]
            pure = page_images.get(first_page)
            if pure and _has_front_semantics(_semantic_text(first_page, pure[1])):
                front_resource, front_page = pure[0], first_page

        if front_resource and front_page is None:
            pages = resource_pages.get(front_resource, [])
            if pages:
                front_page = pages[0]

        back_resource: str | None = None
        back_page: str | None = None
        back_confidence = CoverConfidence.NONE
        back_reasons: list[str] = []

        for source_name, semantics, href in explicit_references:
            if not _has_back_semantics(semantics):
                continue
            if source_name == "landmarks":
                resource, page = _resolve_reference("", href, manifest_by_href, page_images)
            else:
                resource, page = _resolve_reference(opf_path, href, manifest_by_href, page_images)
            if resource:
                back_resource, back_page = resource, page
                back_confidence = CoverConfidence.HIGH
                back_reasons.append(f"{source_name} 明確標示封底")
                break

        if back_resource is None:
            for item in manifest.values():
                if not _has_back_semantics(_semantic_text(item.id, item.href, " ".join(item.properties))):
                    continue
                if _is_image(item):
                    back_resource = item.href
                    pages = resource_pages.get(item.href, [])
                    back_page = pages[-1] if pages else None
                elif _is_document(item) and item.href in page_images:
                    back_resource, _semantics = page_images[item.href]
                    back_page = item.href
                else:
                    continue
                back_confidence = CoverConfidence.HIGH
                back_reasons.append("manifest 名稱或屬性明確標示封底")
                break

        if back_resource is None and spine_documents:
            final_page = spine_documents[-1]
            pure = page_images.get(final_page)
            if pure and _has_back_semantics(_semantic_text(final_page, pure[1])):
                back_resource, back_page = pure[0], final_page
                back_confidence = CoverConfidence.HIGH
                back_reasons.append("閱讀順序末端的純圖片頁明確命名為封底")

        if back_resource is None and spine_documents:
            final_page = spine_documents[-1]
            pure = page_images.get(final_page)
            if pure and pure[0] != front_resource:
                if _similar_dimensions(
                    _image_dimensions(archive, front_resource, names),
                    _image_dimensions(archive, pure[0], names),
                ):
                    back_resource, back_page = pure[0], final_page
                    if _has_barcode_pattern(archive, pure[0], names):
                        back_confidence = CoverConfidence.HIGH
                        back_reasons.append("閱讀順序末端純圖片頁包含條碼圖樣")
                    else:
                        back_confidence = CoverConfidence.MEDIUM
                        back_reasons.append("閱讀順序末端純圖片頁與正面封面尺寸相近")

        front_pages: list[str] = []
        if front_page:
            front_pages.append(front_page)
        for page in resource_pages.get(front_resource or "", []):
            if page not in front_pages and page != back_page:
                front_pages.append(page)
        final_spine_page = spine_documents[-1] if spine_documents else None
        for page in spine_documents[:5]:
            if page == final_spine_page or page == back_page or page in front_pages:
                continue
            pure = page_images.get(page)
            if pure and _visually_similar_images(
                archive,
                front_resource,
                pure[0],
                names,
            ):
                front_pages.append(page)

        return EpubStructure(
            opf_path=opf_path,
            manifest=manifest,
            spine_ids=spine_ids,
            spine_documents=spine_documents,
            detection=EpubCoverDetection(
                front_resource=front_resource,
                front_page=front_page,
                front_pages=tuple(front_pages),
                back_resource=back_resource,
                back_page=back_page,
                back_confidence=back_confidence,
                back_reasons=tuple(back_reasons),
            ),
        )
