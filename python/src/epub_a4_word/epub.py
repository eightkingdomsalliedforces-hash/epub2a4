from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urldefrag
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup, NavigableString, Tag

from .epub_structure import inspect_epub_structure
from .models import ImageBlock, PageBreakBlock, ParsedBook, TextBlock, TextRun
from .pagination import LayoutSettings, paginate


class EpubError(ValueError):
    """Raised when an EPUB package cannot be parsed."""


def _normalized_archive_path(base_file: str, href: str) -> str:
    href, _fragment = urldefrag(unquote(href or ""))
    href = href.replace("\\", "/")
    base = posixpath.dirname(base_file)
    normalized = posixpath.normpath(posixpath.join(base, href))
    return normalized.lstrip("/")


def _first_text(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _inline_runs(element: Tag) -> tuple[TextRun, ...]:
    runs: list[TextRun] = []

    def append_text(text: str, bold: bool, italic: bool) -> None:
        if not text:
            return
        if runs and runs[-1].bold == bold and runs[-1].italic == italic:
            previous = runs[-1]
            runs[-1] = TextRun(previous.text + text, bold, italic)
        else:
            runs.append(TextRun(text=text, bold=bold, italic=italic))

    def visit(node: Tag | NavigableString, bold: bool = False, italic: bool = False) -> None:
        if isinstance(node, NavigableString):
            # XHTML indentation/newlines become one ordinary space while meaningful
            # leading/trailing spaces around inline formatting are retained.
            append_text(re.sub(r"\s+", " ", str(node)), bold, italic)
            return
        if not isinstance(node, Tag):
            return
        name = (node.name or "").lower()
        next_bold = bold or name in {"b", "strong"}
        next_italic = italic or name in {"i", "em"}
        if name == "br":
            append_text("\n", next_bold, next_italic)
            return
        if name in {"img", "image", "svg"}:
            return
        for child in node.children:
            visit(child, next_bold, next_italic)

    for child in element.children:
        visit(child)

    if not runs:
        return ()
    first = runs[0]
    runs[0] = TextRun(first.text.lstrip(), first.bold, first.italic)
    last = runs[-1]
    runs[-1] = TextRun(last.text.rstrip(), last.bold, last.italic)
    return tuple(run for run in runs if run.text)


def _image_href(tag: Tag) -> str:
    return (
        tag.get("src")
        or tag.get("href")
        or tag.get("xlink:href")
        or tag.attrs.get("{http://www.w3.org/1999/xlink}href")
        or ""
    )


def _xhtml_blocks(soup: BeautifulSoup, document_path: str, available: set[str], warnings: list[str]):
    body = soup.body or soup
    terminal_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "li", "pre", "figcaption"}
    container_tags = {"body", "div", "section", "article", "main", "nav", "figure", "ul", "ol"}

    def resolve_image(tag: Tag, page_break_before: bool = False) -> ImageBlock | None:
        href = _image_href(tag)
        if not href and (tag.name or "").lower() == "svg":
            inner = tag.find("image")
            href = _image_href(inner) if inner else ""
            if inner is not None and not tag.get("alt"):
                tag = inner
        if not href:
            return None
        resolved = _normalized_archive_path(document_path, href)
        if resolved not in available:
            warnings.append(f"找不到圖片資源：{resolved}")
            return None
        return ImageBlock(resolved, tag.get("alt", ""), page_break_before=page_break_before)

    def inline_items(node: Tag | NavigableString, bold: bool = False, italic: bool = False):
        if isinstance(node, NavigableString):
            text = re.sub(r"\s+", " ", str(node))
            if text:
                yield TextRun(text, bold, italic)
            return
        if not isinstance(node, Tag):
            return
        name = (node.name or "").lower()
        next_bold = bold or name in {"b", "strong"}
        next_italic = italic or name in {"i", "em"}
        if name == "br":
            yield TextRun("\n", next_bold, next_italic)
            return
        if name in {"img", "image", "svg"}:
            yield node
            return
        for child in node.children:
            yield from inline_items(child, next_bold, next_italic)

    def normalize_runs(runs: list[TextRun]) -> tuple[TextRun, ...]:
        merged: list[TextRun] = []
        for run in runs:
            if not run.text:
                continue
            if merged and merged[-1].bold == run.bold and merged[-1].italic == run.italic:
                previous = merged[-1]
                merged[-1] = TextRun(previous.text + run.text, run.bold, run.italic)
            else:
                merged.append(run)
        if not merged:
            return ()
        first = merged[0]
        merged[0] = TextRun(first.text.lstrip(), first.bold, first.italic)
        last = merged[-1]
        merged[-1] = TextRun(last.text.rstrip(), last.bold, last.italic)
        return tuple(run for run in merged if run.text)

    def emit_terminal(element: Tag):
        name = (element.name or "").lower()
        style_attr = (element.get("style") or "").lower()
        class_attr = " ".join(element.get("class") or []).lower()
        break_before = (
            "page-break-before" in style_attr
            or "break-before" in style_attr
            or "pagebreak" in class_attr
        )
        style = "heading" if name.startswith("h") else ("quote" if name == "blockquote" else "body")
        pending: list[TextRun] = []
        first_item = True

        def flush_text():
            nonlocal pending, first_item
            runs = normalize_runs(pending)
            pending = []
            if runs and any(run.text.strip() for run in runs):
                block = TextBlock(runs, style=style, page_break_before=break_before and first_item)
                first_item = False
                return block
            return None

        for child in element.children:
            for item in inline_items(child):
                if isinstance(item, TextRun):
                    pending.append(item)
                else:
                    text_block = flush_text()
                    if text_block is not None:
                        yield text_block
                    image_block = resolve_image(item, page_break_before=break_before and first_item)
                    if image_block is not None:
                        first_item = False
                        yield image_block
        text_block = flush_text()
        if text_block is not None:
            yield text_block

    def walk(node: Tag | NavigableString):
        if isinstance(node, NavigableString):
            text = re.sub(r"\s+", " ", str(node)).strip()
            if text:
                yield TextBlock((TextRun(text),), style="body")
            return
        if not isinstance(node, Tag):
            return
        name = (node.name or "").lower()
        if name in {"img", "image", "svg"}:
            image = resolve_image(node)
            if image is not None:
                yield image
            return
        if name in terminal_tags:
            yield from emit_terminal(node)
            return
        if name in container_tags or node is body:
            for child in node.children:
                yield from walk(child)
            return
        # Unknown structural tags are treated as transparent containers.
        for child in node.children:
            yield from walk(child)

    yield from walk(body)


def parse_epub(
    path: Path | str,
    *,
    content_only: bool = True,
    confirmed_back_cover_page: str | None = None,
) -> ParsedBook:
    source = Path(path)
    if not source.exists():
        raise EpubError(f"找不到 EPUB：{source}")

    try:
        structure = inspect_epub_structure(source)
        archive = ZipFile(source)
    except BadZipFile as exc:
        raise EpubError("檔案不是有效的 EPUB/ZIP。") from exc
    except ValueError as exc:
        raise EpubError(str(exc)) from exc

    with archive:
        if not structure.spine_ids:
            raise EpubError("EPUB 沒有可讀取的書脊順序。")
        names = set(archive.namelist())
        try:
            package = BeautifulSoup(archive.read(structure.opf_path), "xml")
        except KeyError as exc:
            raise EpubError(f"EPUB 缺少套件檔：{structure.opf_path}") from exc

        book = ParsedBook(source_path=source)
        metadata = package.find("metadata")
        if metadata:
            book.title = _first_text(metadata.find(lambda tag: tag.name and tag.name.split(":")[-1] == "title"))
            book.author = _first_text(metadata.find(lambda tag: tag.name and tag.name.split(":")[-1] == "creator"))
            book.language = _first_text(metadata.find(lambda tag: tag.name and tag.name.split(":")[-1] == "language"))

        for item in structure.manifest.values():
            if item.href in names and (
                item.media_type.startswith("image/")
                or item.href.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"))
            ):
                book.resources[item.href] = archive.read(item.href)
                book.media_types[item.href] = item.media_type

        excluded_pages: set[str] = set()
        if content_only:
            detection = structure.detection
            excluded_pages.update(detection.front_pages)
            if detection.back_confidence.value == "high" and detection.back_page:
                excluded_pages.add(detection.back_page)
            if confirmed_back_cover_page:
                excluded_pages.add(confirmed_back_cover_page)

        emitted_document = False
        for item_id in structure.spine_ids:
            item = structure.manifest.get(item_id)
            if item is None:
                book.warnings.append(f"書脊項目不存在於 manifest：{item_id}")
                continue
            document_path, media_type = item.href, item.media_type
            if document_path in excluded_pages:
                continue
            if document_path not in names:
                book.warnings.append(f"找不到章節檔案：{document_path}")
                continue
            raw = archive.read(document_path)
            parser = "xml" if "xml" in media_type else "lxml"
            soup = BeautifulSoup(raw, parser)
            document_blocks = list(_xhtml_blocks(soup, document_path, names, book.warnings))
            if not document_blocks:
                continue
            if emitted_document:
                book.blocks.append(PageBreakBlock())
            book.blocks.extend(document_blocks)
            emitted_document = True

        # Some EPUBs omit image resources from the manifest. Retain referenced image bytes anyway.
        for block in book.blocks:
            if isinstance(block, ImageBlock) and block.resource_path not in book.resources and block.resource_path in names:
                book.resources[block.resource_path] = archive.read(block.resource_path)
                suffix = PurePosixPath(block.resource_path).suffix.lower()
                book.media_types[block.resource_path] = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                }.get(suffix, "application/octet-stream")

        return book


def estimate_epub_page_count(
    source_path: Path | str,
    settings: LayoutSettings,
    *,
    content_only: bool = True,
    confirmed_back_cover_page: str | None = None,
) -> int:
    """Estimate logical pages when cover editing starts directly from an EPUB."""

    book = parse_epub(
        source_path,
        content_only=content_only,
        confirmed_back_cover_page=confirmed_back_cover_page,
    )
    pages = paginate(book.blocks, settings, image_sizes={})
    return max(1, len(pages))
