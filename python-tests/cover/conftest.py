from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from docx import Document
from PIL import Image
from pypdf import PdfWriter


def _png_bytes(width: int = 12, height: int = 18) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def _build_epub(path: Path, *, epub2_cover: bool = False) -> None:
    cover_meta = '<meta name="cover" content="cover-item"/>' if epub2_cover else ""
    cover_properties = "" if epub2_cover else ' properties="cover-image"'
    container_xml = """<?xml version="1.0"?>
    <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
      <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
    </container>
    """
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
    <package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0" unique-identifier="book-id">
      <metadata>
        <dc:title>測試 EPUB</dc:title>
        <dc:creator>測試作者</dc:creator>
        <dc:description>封底簡介</dc:description>
        <dc:identifier id="book-id">urn:isbn:9780000000001</dc:identifier>
        <dc:publisher>測試出版社</dc:publisher>
        <dc:language>zh-TW</dc:language>
        {cover_meta}
      </metadata>
      <manifest>
        <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
        <item id="cover-item" href="images/cover.png" media-type="image/png"{cover_properties}/>
        <item id="other-image" href="images/other.png" media-type="image/png"/>
      </manifest>
      <spine><itemref idref="chapter"/></spine>
    </package>
    """
    chapter = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
    <h1>第一章</h1><p>這是一小段測試文字。</p>
    </body></html>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr("META-INF/container.xml", container_xml, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/chapter.xhtml", chapter, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/images/cover.png", _png_bytes(), compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/images/other.png", _png_bytes(4, 5), compress_type=ZIP_DEFLATED)


def _replace_zip_member(path: Path, member: str, data: bytes) -> None:
    replacement = path.with_suffix(path.suffix + ".tmp")
    with ZipFile(path, "r") as source, ZipFile(replacement, "w") as target:
        for item in source.infolist():
            payload = data if item.filename == member else source.read(item.filename)
            target.writestr(item, payload)
    replacement.replace(path)


def _build_docx(path: Path, *, pages: str = "12") -> None:
    document = Document()
    document.add_paragraph("測試內容")
    document.core_properties.title = "測試 DOCX"
    document.core_properties.author = "Word 作者"
    document.core_properties.comments = "Word 簡介"
    document.core_properties.identifier = "9780000000002"
    document.core_properties.language = "zh-TW"
    document.save(path)
    with ZipFile(path, "r") as archive:
        app_xml = archive.read("docProps/app.xml").decode("utf-8")
    if "<Pages>" in app_xml:
        before, remainder = app_xml.split("<Pages>", 1)
        _old, after = remainder.split("</Pages>", 1)
        app_xml = f"{before}<Pages>{pages}</Pages>{after}"
    else:
        app_xml = app_xml.replace("</Properties>", f"<Pages>{pages}</Pages></Properties>")
    _replace_zip_member(path, "docProps/app.xml", app_xml.encode("utf-8"))


def _build_pdf(path: Path, *, encrypted: bool = False) -> None:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=72, height=72)
    writer.add_metadata(
        {
            "/Title": "測試 PDF",
            "/Author": "PDF 作者",
            "/Subject": "PDF 簡介",
            "/Keywords": "9780000000003",
        }
    )
    if encrypted:
        writer.encrypt("secret")
    with path.open("wb") as output:
        writer.write(output)


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    cover = tmp_path / "cover"
    cover.mkdir()
    _build_epub(cover / "metadata.epub")
    _build_epub(cover / "metadata-epub2.epub", epub2_cover=True)
    _build_docx(cover / "metadata.docx")
    _build_docx(cover / "metadata-invalid-pages.docx", pages="unknown")
    _build_pdf(cover / "metadata.pdf")
    _build_pdf(cover / "metadata-encrypted.pdf", encrypted=True)
    return tmp_path

from dataclasses import replace
from typing import Callable

from epub_a4_word.cover.models import CoverMetadata, CoverProject, ImageMode, TrimSize


@pytest.fixture
def sample_project(tmp_path: Path) -> Callable[..., CoverProject]:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub-placeholder")

    def factory(
        *,
        trim: tuple[float, float] = (105.0, 148.0),
        page_count: int = 160,
        paper_caliper_mm: float = 0.10,
        manual_spine_width_mm: float | None = None,
        bleed_mm: float = 3.0,
    ) -> CoverProject:
        return CoverProject(
            schema_version=1,
            source_file=str(source),
            source_type="epub",
            metadata=CoverMetadata(
                title="範例書名",
                author="範例作者",
                description="這是封底說明文字。",
                isbn="9780000000000",
                publisher="範例出版社",
                language="zh-TW",
            ),
            trim_size=TrimSize(*trim),
            page_count=page_count,
            paper_caliper_mm=paper_caliper_mm,
            manual_spine_width_mm=manual_spine_width_mm,
            bleed_mm=bleed_mm,
            overlap_mm=5.0,
            image_mode=ImageMode.FRONT_ONLY,
        )

    return factory
