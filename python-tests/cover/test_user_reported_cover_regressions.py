from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from epub_a4_word.cover.metadata import inspect_metadata
from epub_a4_word.cover.models import (
    CoverElement,
    CoverMetadata,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
    TrimSize,
)
from epub_a4_word.cover.templates import apply_template


def _write_epub(path: Path, identifiers: list[tuple[str, str]]) -> None:
    identifier_xml = "".join(
        f'<dc:identifier id="{identifier_id}">{value}</dc:identifier>'
        for identifier_id, value in identifiers
    )
    opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>測試書</dc:title>
    <dc:creator>作者</dc:creator>
    <dc:language>zh-TW</dc:language>
    {identifier_xml}
  </metadata>
  <manifest />
  <spine />
</package>
'''
    container = '''<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" />
  </rootfiles>
</container>
'''
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)


def _project_with_embedded_front_cover(tmp_path: Path) -> CoverProject:
    cover_path = tmp_path / "cover.png"
    cover_path.write_bytes(b"placeholder")
    return CoverProject(
        schema_version=1,
        source_file=str(tmp_path / "book.epub"),
        source_type="epub",
        metadata=CoverMetadata(
            title="魔法禁書目錄 1",
            author="鎌池和馬",
            description="封底簡介",
            isbn="9780000000001",
            publisher="KADOKAWA",
        ),
        trim_size=TrimSize(148.0, 210.0),
        page_count=160,
        paper_caliper_mm=0.085,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path),
        elements=(
            CoverElement(
                id="source-cover-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(160.8, 3.0, 148.0, 210.0),
                z_index=-15,
                content={"path": str(cover_path), "fit": "cover"},
            ),
        ),
    )


def test_legacy_desktop_template_ids_are_accepted(tmp_path: Path) -> None:
    project = _project_with_embedded_front_cover(tmp_path)
    aliases = {
        "minimal": "source_cover_only",
        "full_bleed_image": "full_spread",
        "classic_book": "minimal_text",
    }
    for legacy_id, canonical_id in aliases.items():
        legacy = apply_template(project, legacy_id)
        canonical = apply_template(project, canonical_id)
        assert legacy == canonical


def test_epub_identifier_prefers_real_isbn_over_unique_uuid(tmp_path: Path) -> None:
    epub = tmp_path / "uuid-and-isbn.epub"
    _write_epub(
        epub,
        [
            ("book-id", "35e130a1-61a1-4f1a-ad90-e5eacf13b7a0"),
            ("isbn", "978-4-04-866304-0"),
        ],
    )
    assert inspect_metadata(epub).metadata.isbn == "9784048663040"


def test_epub_identifier_does_not_show_uuid_as_barcode_text(tmp_path: Path) -> None:
    epub = tmp_path / "uuid-only.epub"
    _write_epub(epub, [("book-id", "35e130a1-61a1-4f1a-ad90-e5eacf13b7a0")])
    assert inspect_metadata(epub).metadata.isbn == ""


def test_front_image_template_does_not_duplicate_title_over_embedded_cover(tmp_path: Path) -> None:
    result = apply_template(_project_with_embedded_front_cover(tmp_path), "front_image_plain_back")
    assert "source-cover-image" in result.elements_by_id
    assert "front-title" not in result.elements_by_id
    assert "front-author" not in result.elements_by_id
    assert "back-description" in result.elements_by_id
    assert "spine-title" in result.elements_by_id


def test_full_spread_template_starts_without_text_overlays(tmp_path: Path) -> None:
    result = apply_template(_project_with_embedded_front_cover(tmp_path), "full_spread")
    assert "front-title" not in result.elements_by_id
    assert "front-author" not in result.elements_by_id
    assert "back-description" not in result.elements_by_id
    assert "spine-title" not in result.elements_by_id
