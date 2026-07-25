from __future__ import annotations

from zipfile import ZipFile

from lxml import etree

from epub_a4_word.docx_writer import write_docx
from epub_a4_word.models import TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, MiniPage


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _page(number: int) -> MiniPage:
    return MiniPage(
        blocks=[TextBlock((TextRun(f"第 {number} 頁"),), style="body")],
        used_points=20.0,
        logical_page_number=number,
    )


def test_b6_uses_one_multirow_table_without_standalone_prefix_paragraphs(tmp_path) -> None:
    output = tmp_path / "b6.docx"
    write_docx(
        [_page(1), _page(2)],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(imposition_mode="b6_on_a5"),
        imposition_mode="b6_on_a5",
    )

    with ZipFile(output) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))

    body = document.find(f"{{{W_NS}}}body")
    assert body is not None
    top_level = [etree.QName(child).localname for child in body]
    assert top_level == ["tbl", "sectPr"]
    assert int(document.xpath("count(.//w:tbl)", namespaces={"w": W_NS})) == 1
    assert int(document.xpath("count(.//w:tbl/w:tr)", namespaces={"w": W_NS})) == 2
