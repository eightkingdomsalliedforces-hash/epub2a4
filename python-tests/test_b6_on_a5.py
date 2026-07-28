from __future__ import annotations

from zipfile import ZipFile

import pytest
from docx import Document

from epub_a4_word.docx_writer import write_docx
from epub_a4_word.imposition import build_imposition
from epub_a4_word.models import TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, MiniPage, resolve_layout


def _page() -> MiniPage:
    page = MiniPage(
        blocks=[TextBlock((TextRun("可編輯的 B6 內容"),), style="body")],
        used_points=20.0,
        logical_page_number=1,
    )
    return page


def test_b6_content_is_anchored_to_a5_bottom_right():
    resolved = resolve_layout(LayoutSettings(imposition_mode="b6_on_a5"))
    assert resolved.paper_width_cm == pytest.approx(14.8)
    assert resolved.paper_height_cm == pytest.approx(21.0)
    assert resolved.cell_width_cm == pytest.approx(12.8)
    assert resolved.cell_height_cm == pytest.approx(18.2)
    assert resolved.page_margin_left_cm == pytest.approx(2.0)
    assert resolved.page_margin_right_cm == pytest.approx(0.0)
    assert resolved.page_margin_top_cm == pytest.approx(2.8)
    assert resolved.page_margin_bottom_cm == pytest.approx(0.0)
    assert build_imposition(3, "b6_on_a5").sides == ((1,), (2,), (3,))


def test_crop_mark_mode_adds_only_page_local_top_and_left_guides(tmp_path):
    normal = tmp_path / "normal.docx"
    marked = tmp_path / "marked.docx"
    for output, mark_mode in ((normal, "normal"), (marked, "crop_marks")):
        write_docx(
            [_page()],
            output,
            resources={},
            media_types={},
            settings=LayoutSettings(
                imposition_mode="b6_on_a5",
                output_mark_mode=mark_mode,
            ),
            imposition_mode="b6_on_a5",
        )

    document = Document(marked)
    assert document.sections[0].page_width.mm == pytest.approx(148.0, abs=0.2)
    assert document.sections[0].page_height.mm == pytest.approx(210.0, abs=0.2)

    def document_xml(path):
        with ZipFile(path) as archive:
            return archive.read("word/document.xml")

    assert document_xml(normal).count(b"<v:line") == 0
    assert document_xml(marked).count(b"<v:line") == 2
