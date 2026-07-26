from __future__ import annotations

from pathlib import Path

import pytest

from epub_a4_word.cover.metadata import inspect_metadata
from epub_a4_word.epub import estimate_epub_page_count
from epub_a4_word.pagination import LayoutSettings


def test_epub_reads_opf_metadata_and_embedded_cover(fixtures_dir: Path) -> None:
    result = inspect_metadata(fixtures_dir / "cover/metadata.epub")
    assert result.source_type == "epub"
    assert result.metadata.title == "測試 EPUB"
    assert result.metadata.author == "測試作者"
    assert result.metadata.description == "封底簡介"
    assert result.metadata.isbn == "9780000000001"
    assert result.metadata.publisher == "測試出版社"
    assert result.metadata.language == "zh-TW"
    assert result.fixed_page_count is None
    assert result.metadata.embedded_images[0] == {
        "id": "cover-item",
        "href": "OEBPS/images/cover.png",
        "media_type": "image/png",
        "role": "front_cover",
        "width_px": 12,
        "height_px": 18,
    }
    assert set(result.metadata.embedded_images[1]) == {
        "id",
        "href",
        "media_type",
        "role",
        "width_px",
        "height_px",
    }


def test_epub2_meta_cover_is_detected(fixtures_dir: Path) -> None:
    result = inspect_metadata(fixtures_dir / "cover/metadata-epub2.epub")
    assert result.metadata.embedded_images[0]["id"] == "cover-item"
    assert result.metadata.embedded_images[0]["role"] == "front_cover"


def test_docx_reads_core_properties_and_pages(fixtures_dir: Path) -> None:
    result = inspect_metadata(fixtures_dir / "cover/metadata.docx")
    assert result.source_type == "docx"
    assert result.metadata.title == "測試 DOCX"
    assert result.metadata.author == "Word 作者"
    assert result.metadata.description == "Word 簡介"
    assert result.metadata.isbn == "9780000000002"
    assert result.metadata.language == "zh-TW"
    assert result.fixed_page_count == 12
    assert result.warnings == ()


def test_docx_invalid_pages_returns_warning(fixtures_dir: Path) -> None:
    result = inspect_metadata(fixtures_dir / "cover/metadata-invalid-pages.docx")
    assert result.fixed_page_count is None
    assert any("頁數" in warning for warning in result.warnings)


def test_pdf_reads_document_info_and_actual_pages(fixtures_dir: Path) -> None:
    result = inspect_metadata(fixtures_dir / "cover/metadata.pdf")
    assert result.source_type == "pdf"
    assert result.metadata.title == "測試 PDF"
    assert result.metadata.author == "PDF 作者"
    assert result.metadata.description == "PDF 簡介"
    assert result.metadata.isbn == "9780000000003"
    assert result.fixed_page_count == 3


def test_encrypted_pdf_without_empty_password_is_rejected(fixtures_dir: Path) -> None:
    with pytest.raises(ValueError, match="無法讀取加密 PDF"):
        inspect_metadata(fixtures_dir / "cover/metadata-encrypted.pdf")


def test_unsupported_and_missing_sources_are_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing.epub"
    with pytest.raises(ValueError, match="找不到來源文件"):
        inspect_metadata(missing)
    other = tmp_path / "book.txt"
    other.write_text("text", encoding="utf-8")
    with pytest.raises(ValueError, match="只支援 EPUB、DOCX 或 PDF"):
        inspect_metadata(other)


def test_estimate_epub_page_count_returns_at_least_one(fixtures_dir: Path) -> None:
    count = estimate_epub_page_count(
        fixtures_dir / "cover/metadata.epub",
        LayoutSettings(imposition_mode="single_a5"),
    )
    assert count == 1



def _build_front_back_epub(path: Path, *, generic_back: bool = False) -> Path:
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

    from PIL import Image

    def png() -> bytes:
        output = BytesIO()
        Image.new("RGB", (600, 900), "white").save(output, format="PNG")
        return output.getvalue()

    back_id = "plate-page" if generic_back else "back-cover-page"
    back_href = "plate.xhtml" if generic_back else "back-cover.xhtml"
    guide = "" if generic_back else "<guide><reference type='back-cover' href='Text/back-cover.xhtml'/></guide>"
    container = """<?xml version='1.0'?>
    <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
      <rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>
    </container>"""
    opf = f"""<?xml version='1.0' encoding='utf-8'?>
    <package xmlns='http://www.idpf.org/2007/opf' xmlns:dc='http://purl.org/dc/elements/1.1/' version='3.0'>
      <metadata><dc:title>前後封面測試</dc:title></metadata>
      <manifest>
        <item id='front-page' href='Text/front.xhtml' media-type='application/xhtml+xml'/>
        <item id='chapter' href='Text/chapter.xhtml' media-type='application/xhtml+xml'/>
        <item id='{back_id}' href='Text/{back_href}' media-type='application/xhtml+xml'/>
        <item id='front-image' href='Images/front.png' media-type='image/png' properties='cover-image'/>
        <item id='back-image' href='Images/back.png' media-type='image/png'/>
      </manifest>
      <spine><itemref idref='front-page'/><itemref idref='chapter'/><itemref idref='{back_id}'/></spine>
      {guide}
    </package>"""
    front = "<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/front.png'/></body></html>"
    chapter = "<html xmlns='http://www.w3.org/1999/xhtml'><body><p>正文</p></body></html>"
    back = "<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/back.png'/></body></html>"
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr("META-INF/container.xml", container, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/Text/front.xhtml", front, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/Text/chapter.xhtml", chapter, compress_type=ZIP_DEFLATED)
        archive.writestr(f"OEBPS/Text/{back_href}", back, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/Images/front.png", png(), compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/Images/back.png", png(), compress_type=ZIP_DEFLATED)
    return path


def test_epub_metadata_assigns_front_and_high_confidence_back_roles(tmp_path: Path) -> None:
    result = inspect_metadata(_build_front_back_epub(tmp_path / "front-back.epub"))
    roles = {item["href"]: item["role"] for item in result.metadata.embedded_images}
    assert roles["OEBPS/Images/front.png"] == "front_cover"
    assert roles["OEBPS/Images/back.png"] == "back_cover"


def test_epub_metadata_marks_medium_back_as_candidate(tmp_path: Path) -> None:
    result = inspect_metadata(
        _build_front_back_epub(tmp_path / "candidate.epub", generic_back=True)
    )
    roles = {item["href"]: item["role"] for item in result.metadata.embedded_images}
    assert roles["OEBPS/Images/front.png"] == "front_cover"
    assert roles["OEBPS/Images/back.png"] == "back_cover_candidate"
