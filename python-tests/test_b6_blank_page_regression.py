from __future__ import annotations

from zipfile import ZipFile

import pytest
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


def test_b6_uses_mirrored_rows_and_one_minimal_terminal_paragraph(tmp_path) -> None:
    output = tmp_path / "b6.docx"
    write_docx(
        [_page(1), _page(2)],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode="b6_on_a5",
            output_mark_mode="crop_marks",
        ),
        imposition_mode="b6_on_a5",
    )

    with ZipFile(output) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))

    body = document.find(f"{{{W_NS}}}body")
    assert body is not None
    top_level = [etree.QName(child).localname for child in body]
    assert top_level == ["tbl", "p", "sectPr"]
    assert int(document.xpath("count(.//w:body/w:tbl)", namespaces={"w": W_NS})) == 1
    assert int(document.xpath("count(.//w:body/w:tbl/w:tr)", namespaces={"w": W_NS})) == 2
    assert int(document.xpath("count(.//w:pageBreakBefore)", namespaces={"w": W_NS})) == 0
    assert document.xpath(
        ".//w:body/w:p[last()]/w:pPr/w:spacing[@w:line='1'][@w:lineRule='exact']",
        namespaces={"w": W_NS},
    )
    assert int(document.xpath(
        "count(.//w:body/w:p/w:pPr/w:spacing[@w:line='1'][@w:lineRule='exact'])",
        namespaces={"w": W_NS},
    )) == 1
    row_heights = [
        int(value)
        for value in document.xpath(
            ".//w:body/w:tbl/w:tr/w:trPr/w:trHeight/@w:val",
            namespaces={"w": W_NS},
        )
    ]
    assert row_heights[0] - row_heights[-1] == pytest.approx(
        0.3 * 1440 / 2.54,
        abs=1,
    )
