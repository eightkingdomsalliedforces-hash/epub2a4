from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
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


@pytest.mark.parametrize("mode", ["single_a5", "single_4x6", "b6_on_a5"])
def test_single_page_modes_use_mirrored_rows_and_one_minimal_terminal_paragraph(
    tmp_path: Path, mode: str
) -> None:
    output = tmp_path / f"{mode}.docx"
    write_docx(
        [_page(1), _page(2), _page(3)],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(imposition_mode=mode),
        imposition_mode=mode,
    )

    with ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))

    body = root.find(f"{{{W_NS}}}body")
    assert body is not None
    assert [etree.QName(child).localname for child in body] == [
        "tbl",
        "p",
        "sectPr",
    ]
    assert int(root.xpath("count(.//w:body/w:tbl)", namespaces={"w": W_NS})) == 1
    assert int(root.xpath("count(.//w:body/w:tbl/w:tr)", namespaces={"w": W_NS})) == 3
    assert int(root.xpath("count(.//w:pageBreakBefore)", namespaces={"w": W_NS})) == 0
    assert root.xpath(
        ".//w:body/w:p[last()]/w:pPr/w:spacing[@w:line='1'][@w:lineRule='exact']",
        namespaces={"w": W_NS},
    )


@pytest.mark.parametrize(
    ("mode", "expected_width_cm", "expected_height_cm"),
    [
        ("single_a5", 14.8, 21.0),
        ("single_4x6", 10.16, 15.24),
        ("b6_on_a5", 14.8, 21.0),
    ],
)
def test_single_page_modes_write_exact_physical_page_size(
    tmp_path: Path,
    mode: str,
    expected_width_cm: float,
    expected_height_cm: float,
) -> None:
    output = tmp_path / f"{mode}-size.docx"
    write_docx(
        [_page(1)],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(imposition_mode=mode),
        imposition_mode=mode,
    )

    section = Document(output).sections[0]
    assert abs(section.page_width.cm - expected_width_cm) < 0.02
    assert abs(section.page_height.cm - expected_height_cm) < 0.02


@pytest.mark.parametrize(
    ("mode", "expected_width_pt", "expected_height_pt"),
    [
        ("single_a5", 419.5, 595.3),
        ("single_4x6", 288.0, 432.0),
        ("b6_on_a5", 419.5, 595.3),
    ],
)
def test_single_page_modes_render_three_content_pages_as_three_physical_pages(
    tmp_path: Path,
    mode: str,
    expected_width_pt: float,
    expected_height_pt: float,
) -> None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdfinfo = shutil.which("pdfinfo")
    if not soffice or not pdfinfo:
        pytest.skip("LibreOffice/pdfinfo not installed")

    output = tmp_path / f"{mode}-render.docx"
    write_docx(
        [_page(1), _page(2), _page(3)],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(imposition_mode=mode),
        imposition_mode=mode,
    )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    info = subprocess.run(
        [pdfinfo, str(tmp_path / f"{mode}-render.pdf")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    pages_match = re.search(r"^Pages:\s+(\d+)$", info, re.MULTILINE)
    size_match = re.search(
        r"^Page size:\s+([0-9.]+) x ([0-9.]+) pts", info, re.MULTILINE
    )
    assert pages_match is not None
    assert int(pages_match.group(1)) == 3
    assert size_match is not None
    width_pt = float(size_match.group(1))
    height_pt = float(size_match.group(2))
    assert abs(width_pt - expected_width_pt) < 1.0
    assert abs(height_pt - expected_height_pt) < 1.0
