from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urldefrag
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup, NavigableString, Tag

from .models import ImageBlock, PageBreakBlock, ParsedBook, TextBlock, TextRun


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


def parse_epub(path: Path | str) -> ParsedBook:
    source = Path(path)
    if not source.exists():
        raise EpubError(f"找不到 EPUB：{source}")

    try:
        archive = ZipFile(source)
    except BadZipFile as exc:
        raise EpubError("檔案不是有效的 EPUB/ZIP。") from exc

    with archive:
        names = set(archive.namelist())
        try:
            container = BeautifulSoup(archive.read("META-INF/container.xml"), "xml")
        except KeyError as exc:
            raise EpubError("EPUB 缺少 META-INF/container.xml。") from exc
        rootfile = container.find("rootfile")
        if rootfile is None or not rootfile.get("full-path"):
            raise EpubError("EPUB container.xml 沒有 OPF 路徑。")
        opf_path = str(rootfile.get("full-path"))
        try:
            package = BeautifulSoup(archive.read(opf_path), "xml")
        except KeyError as exc:
            raise EpubError(f"EPUB 缺少套件檔：{opf_path}") from exc

        book = ParsedBook(source_path=source)
        metadata = package.find("metadata")
        if metadata:
            book.title = _first_text(metadata.find(lambda tag: tag.name and tag.name.split(":")[-1] == "title"))
            book.author = _first_text(metadata.find(lambda tag: tag.name and tag.name.split(":")[-1] == "creator"))
            book.language = _first_text(metadata.find(lambda tag: tag.name and tag.name.split(":")[-1] == "language"))

        manifest: dict[str, tuple[str, str]] = {}
        for item in package.find_all("item"):
            item_id = item.get("id")
            href = item.get("href")
            if not item_id or not href:
                continue
            resolved = _normalized_archive_path(opf_path, href)
            manifest[item_id] = (resolved, item.get("media-type", ""))
            if resolved in names and (item.get("media-type", "").startswith("image/") or resolved.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"))):
                book.resources[resolved] = archive.read(resolved)
                book.media_types[resolved] = item.get("media-type", "")

        spine = package.find("spine")
        spine_ids = [ref.get("idref") for ref in spine.find_all("itemref")] if spine else []
        if not spine_ids:
            raise EpubError("EPUB 沒有可讀取的書脊順序。")

        for index, item_id in enumerate(spine_ids):
            if not item_id or item_id not in manifest:
                book.warnings.append(f"書脊項目不存在於 manifest：{item_id}")
                continue
            document_path, media_type = manifest[item_id]
            if document_path not in names:
                book.warnings.append(f"找不到章節檔案：{document_path}")
                continue
            if index > 0:
                book.blocks.append(PageBreakBlock())
            raw = archive.read(document_path)
            parser = "xml" if "xml" in media_type else "lxml"
            soup = BeautifulSoup(raw, parser)
            book.blocks.extend(_xhtml_blocks(soup, document_path, names, book.warnings))

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
