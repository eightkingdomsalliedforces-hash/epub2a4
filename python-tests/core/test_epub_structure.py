from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from PIL import Image

from epub_a4_word.epub_structure import CoverConfidence, inspect_epub_structure


def _xhtml(value: str) -> bytes:
    return value.encode("utf-8")


def _png(width: int = 600, height: int = 900) -> bytes:
    out = BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def _build_epub(
    path: Path,
    *,
    epub_version: str = "3.0",
    metadata_extra: str = "",
    manifest_extra: str = "",
    spine_items: tuple[str, ...] = ("chapter",),
    guide: str = "",
    resources: dict[str, bytes] | None = None,
) -> Path:
    resources = dict(resources or {})
    container = """<?xml version='1.0'?>
    <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
      <rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>
    </container>"""
    manifest = """
      <item id='chapter' href='Text/chapter.xhtml' media-type='application/xhtml+xml'/>
    """ + manifest_extra
    spine = "".join(f"<itemref idref='{item}'/>" for item in spine_items)
    opf = f"""<?xml version='1.0' encoding='utf-8'?>
    <package xmlns='http://www.idpf.org/2007/opf' xmlns:dc='http://purl.org/dc/elements/1.1/' version='{epub_version}'>
      <metadata><dc:title>測試書</dc:title><dc:creator>作者</dc:creator>{metadata_extra}</metadata>
      <manifest>{manifest}</manifest>
      <spine>{spine}</spine>
      {guide}
    </package>"""
    resources.setdefault(
        "OEBPS/Text/chapter.xhtml",
        _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>正文</h1><p>內容</p></body></html>"),
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        zf.writestr("META-INF/container.xml", container, compress_type=ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
        for name, data in resources.items():
            zf.writestr(name, data, compress_type=ZIP_DEFLATED)
    return path


def test_epub3_cover_image_and_explicit_guide_back_cover(tmp_path: Path) -> None:
    path = _build_epub(
        tmp_path / "front-back.epub",
        manifest_extra="""
          <item id='front-page' href='Text/front.xhtml' media-type='application/xhtml+xml'/>
          <item id='back-page' href='Text/back.xhtml' media-type='application/xhtml+xml'/>
          <item id='front-image' href='Images/front.png' media-type='image/png' properties='cover-image'/>
          <item id='back-image' href='Images/back.png' media-type='image/png'/>
        """,
        spine_items=("front-page", "chapter", "back-page"),
        guide="""<guide><reference type='back-cover' title='封底' href='Text/back.xhtml'/></guide>""",
        resources={
            "OEBPS/Text/front.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/front.png'/></body></html>"),
            "OEBPS/Text/back.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/back.png'/></body></html>"),
            "OEBPS/Images/front.png": _png(),
            "OEBPS/Images/back.png": _png(),
        },
    )

    structure = inspect_epub_structure(path)

    assert structure.detection.front_resource == "OEBPS/Images/front.png"
    assert structure.detection.front_page == "OEBPS/Text/front.xhtml"
    assert structure.detection.back_resource == "OEBPS/Images/back.png"
    assert structure.detection.back_page == "OEBPS/Text/back.xhtml"
    assert structure.detection.back_confidence is CoverConfidence.HIGH
    assert any("guide" in reason for reason in structure.detection.back_reasons)
    assert structure.spine_documents == (
        "OEBPS/Text/front.xhtml",
        "OEBPS/Text/chapter.xhtml",
        "OEBPS/Text/back.xhtml",
    )


def test_epub2_meta_cover_is_detected_and_linked_to_wrapper_page(tmp_path: Path) -> None:
    path = _build_epub(
        tmp_path / "epub2.epub",
        epub_version="2.0",
        metadata_extra="<meta name='cover' content='cover-image'/>",
        manifest_extra="""
          <item id='cover-page' href='Text/cover.xhtml' media-type='application/xhtml+xml'/>
          <item id='cover-image' href='Images/cover.png' media-type='image/png'/>
        """,
        spine_items=("cover-page", "chapter"),
        resources={
            "OEBPS/Text/cover.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/cover.png'/></body></html>"),
            "OEBPS/Images/cover.png": _png(),
        },
    )

    detection = inspect_epub_structure(path).detection

    assert detection.front_resource == "OEBPS/Images/cover.png"
    assert detection.front_page == "OEBPS/Text/cover.xhtml"


def test_named_final_pure_image_page_is_high_confidence_back_cover(tmp_path: Path) -> None:
    path = _build_epub(
        tmp_path / "named-back.epub",
        manifest_extra="""
          <item id='rear-cover-page' href='Text/rear-cover.xhtml' media-type='application/xhtml+xml'/>
          <item id='rear-cover-image' href='Images/rear-cover.png' media-type='image/png'/>
        """,
        spine_items=("chapter", "rear-cover-page"),
        resources={
            "OEBPS/Text/rear-cover.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><img alt='封底' src='../Images/rear-cover.png'/></body></html>"),
            "OEBPS/Images/rear-cover.png": _png(),
        },
    )

    detection = inspect_epub_structure(path).detection

    assert detection.back_resource == "OEBPS/Images/rear-cover.png"
    assert detection.back_page == "OEBPS/Text/rear-cover.xhtml"
    assert detection.back_confidence is CoverConfidence.HIGH


def test_generic_final_pure_image_is_only_medium_confidence_candidate(tmp_path: Path) -> None:
    path = _build_epub(
        tmp_path / "candidate.epub",
        manifest_extra="""
          <item id='front-page' href='Text/front.xhtml' media-type='application/xhtml+xml'/>
          <item id='last-page' href='Text/plate.xhtml' media-type='application/xhtml+xml'/>
          <item id='front-image' href='Images/front.png' media-type='image/png' properties='cover-image'/>
          <item id='last-image' href='Images/plate.png' media-type='image/png'/>
        """,
        spine_items=("front-page", "chapter", "last-page"),
        resources={
            "OEBPS/Text/front.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/front.png'/></body></html>"),
            "OEBPS/Text/plate.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/plate.png'/></body></html>"),
            "OEBPS/Images/front.png": _png(),
            "OEBPS/Images/plate.png": _png(),
        },
    )

    detection = inspect_epub_structure(path).detection

    assert detection.back_resource == "OEBPS/Images/plate.png"
    assert detection.back_page == "OEBPS/Text/plate.xhtml"
    assert detection.back_confidence is CoverConfidence.MEDIUM


def test_final_page_with_real_text_is_not_a_back_cover_candidate(tmp_path: Path) -> None:
    path = _build_epub(
        tmp_path / "illustration.epub",
        manifest_extra="""
          <item id='last-page' href='Text/ending.xhtml' media-type='application/xhtml+xml'/>
          <item id='last-image' href='Images/ending.png' media-type='image/png'/>
        """,
        spine_items=("chapter", "last-page"),
        resources={
            "OEBPS/Text/ending.xhtml": _xhtml("<html xmlns='http://www.w3.org/1999/xhtml'><body><p>後記正文</p><img src='../Images/ending.png'/></body></html>"),
            "OEBPS/Images/ending.png": _png(),
        },
    )

    detection = inspect_epub_structure(path).detection

    assert detection.back_resource is None
    assert detection.back_page is None
    assert detection.back_confidence is CoverConfidence.NONE
