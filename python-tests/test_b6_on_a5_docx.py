from __future__ import annotations

from zipfile import ZipFile

import pytest
from docx import Document

from epub_a4_word.docx_writer import write_docx
from epub_a4_word.models import TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, MiniPage


def _write_fixture_docx(path, *, output_mark_mode: str) -> None:
    page = MiniPage(
        blocks=[TextBlock((TextRun("可編輯的 B6 內容"),), style="body")],
        logical_page_number=1,
    )
    write_docx(
        [page],
        path,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode="b6_on_a5",
            margin_mode="safe",
            output_mark_mode=output_mark_mode,
        ),
        title="範例書",
        author="作者",
        imposition_mode="b6_on_a5",
    )


def _header_bytes(path) -> bytes:
    with ZipFile(path) as archive:
        return b"".join(
            archive.read(name)
            for name in archive.namelist()
            if name.startswith("word/header") and name.endswith(".xml")
        )


def test_b6_crop_mark_mode_adds_eight_lines_outside_content(tmp_path) -> None:
    normal = tmp_path / "normal.docx"
    marked = tmp_path / "marked.docx"
    _write_fixture_docx(normal, output_mark_mode="normal")
    _write_fixture_docx(marked, output_mark_mode="crop_marks")

    normal_section = Document(normal).sections[0]
    marked_section = Document(marked).sections[0]
    assert normal_section.page_width.mm == pytest.approx(148.0, abs=0.2)
    assert marked_section.page_height.mm == pytest.approx(210.0, abs=0.2)
    assert marked_section.left_margin.mm == pytest.approx(10.0, abs=0.2)
    assert marked_section.right_margin.mm == pytest.approx(10.0, abs=0.2)
    assert marked_section.top_margin.mm == pytest.approx(14.0, abs=0.2)
    assert marked_section.bottom_margin.mm == pytest.approx(14.0, abs=0.2)

    normal_headers = _header_bytes(normal)
    marked_headers = _header_bytes(marked)
    assert normal_headers.count(b"<v:line") == 0
    assert marked_headers.count(b"<v:line") == 8
    assert b"mso-position-horizontal-relative:page" in marked_headers
    assert b"mso-position-vertical-relative:page" in marked_headers
