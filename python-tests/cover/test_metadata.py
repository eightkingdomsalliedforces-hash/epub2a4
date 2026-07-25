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
        "role": "cover",
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
    assert result.metadata.embedded_images[0]["role"] == "cover"


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
