from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from lxml import etree
from PIL import Image

from epub_a4_word.docx_writer import write_docx
from epub_a4_word.models import ImageBlock, TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, MiniPage


_LINE_RE = re.compile(
    rb'<v:line[^>]*from="([0-9.]+)pt,([0-9.]+)pt"[^>]*to="([0-9.]+)pt,([0-9.]+)pt"[^>]*strokeweight="([0-9.]+)pt"[^>]*>(.*?)</v:line>',
    re.DOTALL,
)


def _page(text: str = "測試正文", number: int = 1) -> MiniPage:
    return MiniPage(
        [TextBlock((TextRun(text),), style="body")],
        used_points=20.0,
        logical_page_number=number,
    )


def _write(tmp_path: Path, mode: str, **settings_values) -> Path:
    output = tmp_path / f"{mode}-{len(list(tmp_path.iterdir()))}.docx"
    settings_values.setdefault("guide_render_mode", "vml")
    write_docx(
        [_page()],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(imposition_mode=mode, **settings_values),
        imposition_mode=mode,
    )
    return output


def _header_xml(path: Path) -> bytes:
    with ZipFile(path) as archive:
        return b"".join(
            archive.read(name)
            for name in archive.namelist()
            if name.startswith("word/header") and name.endswith(".xml")
        )


def _document_xml(path: Path) -> bytes:
    with ZipFile(path) as archive:
        return archive.read("word/document.xml")


def _lines_from_payload(payload: bytes):
    return [
        (
            tuple(float(value) for value in match.groups()[:5]),
            match.group(6),
        )
        for match in _LINE_RE.finditer(payload)
    ]


def _lines_from_headers(path: Path):
    return _lines_from_payload(_header_xml(path))


def _lines_from_document(path: Path):
    return _lines_from_payload(_document_xml(path))


def test_b6_docx_uses_bottom_right_content_and_full_cut_lines(tmp_path: Path) -> None:
    output = _write(tmp_path, "b6_on_a5", output_mark_mode="crop_marks")

    section = Document(output).sections[0]
    assert section.page_width.mm == pytest.approx(148.0, abs=0.2)
    assert section.page_height.mm == pytest.approx(210.0, abs=0.2)
    assert section.left_margin.mm == pytest.approx(0.0, abs=0.2)
    assert section.right_margin.mm == pytest.approx(0.0, abs=0.2)
    assert section.top_margin.mm == pytest.approx(28.0, abs=0.2)
    assert section.bottom_margin.mm == pytest.approx(0.0, abs=0.2)

    lines = _lines_from_document(output)
    assert len(lines) == 2
    coordinates = [values[:4] for values, _inner in lines]
    expected = [
        (0.0, 28.0 * 72.0 / 25.4, 148.0 * 72.0 / 25.4, 28.0 * 72.0 / 25.4),
        (20.0 * 72.0 / 25.4, 0.0, 20.0 * 72.0 / 25.4, 210.0 * 72.0 / 25.4),
    ]
    for actual, wanted in zip(coordinates, expected, strict=True):
        assert actual == pytest.approx(wanted, abs=0.01)
    assert [values[4] for values, _inner in lines] == pytest.approx([0.35, 0.35])
    assert all(b"dashstyle" not in inner for _values, inner in lines)
    assert _document_xml(output).count(b"mso-layout-in-cell:f") == 2
    assert _lines_from_headers(output) == []


def test_b6_normal_mode_keeps_position_without_header_guides(tmp_path: Path) -> None:
    output = _write(tmp_path, "b6_on_a5", output_mark_mode="normal")
    section = Document(output).sections[0]
    assert section.left_margin.mm == pytest.approx(0.0, abs=0.2)
    assert section.top_margin.mm == pytest.approx(28.0, abs=0.2)
    assert section.right_margin.mm == pytest.approx(0.0, abs=0.2)
    assert section.bottom_margin.mm == pytest.approx(0.0, abs=0.2)
    assert _lines_from_document(output) == []
    assert _lines_from_headers(output) == []


@pytest.mark.parametrize("mode", ["single_a5", "single_4x6"])
def test_single_sheet_docx_has_no_internal_guides(tmp_path: Path, mode: str) -> None:
    output = _write(tmp_path, mode, output_mark_mode="crop_marks")
    assert _lines_from_headers(output) == []


def test_four_up_docx_uses_two_solid_crop_guides_without_table_borders(
    tmp_path: Path,
) -> None:
    output = _write(tmp_path, "four_up", cut_guides=True)
    lines = _lines_from_headers(output)
    assert len(lines) == 2
    assert all(b"dashstyle" not in inner for _values, inner in lines)
    document_xml = _document_xml(output)
    assert b'<w:insideH w:val="nil"' in document_xml
    assert b'<w:insideV w:val="nil"' in document_xml
    assert b'w:val="dashed"' not in document_xml


def test_signature16_docx_uses_two_dashed_fold_guides(tmp_path: Path) -> None:
    output = _write(tmp_path, "signature16", cut_guides=True)
    lines = _lines_from_headers(output)
    assert len(lines) == 2
    assert all(b'dashstyle="dash"' in inner for _values, inner in lines)
    document_xml = _document_xml(output)
    assert b'<w:insideH w:val="nil"' in document_xml
    assert b'<w:insideV w:val="nil"' in document_xml


def test_grid_docx_can_hide_guides(tmp_path: Path) -> None:
    assert _lines_from_headers(_write(tmp_path, "four_up", cut_guides=False)) == []
    assert _lines_from_headers(_write(tmp_path, "signature16", cut_guides=False)) == []


def test_b6_docx_mirrors_crop_lines_per_page(tmp_path: Path) -> None:
    output = tmp_path / "b6-mirrored-guides.docx"
    pages = [_page("odd page", 1), _page("even page", 2)]
    write_docx(
        pages,
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode="b6_on_a5",
            output_mark_mode="crop_marks",
            writing_mode="taiwan_vertical",
            guide_render_mode="vml",
        ),
        imposition_mode="b6_on_a5",
    )

    lines = _lines_from_document(output)
    assert len(lines) == 4
    vertical_x = [
        values[0]
        for values, _inner in lines
        if values[0] == values[2]
    ]
    assert vertical_x == pytest.approx(
        [20.0 * 72.0 / 25.4, 128.0 * 72.0 / 25.4],
        abs=0.01,
    )
    assert _lines_from_headers(output) == []
    root = etree.fromstring(_document_xml(output))
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    assert int(root.xpath(
        "count(.//w:body/w:p//w:pict)",
        namespaces=namespaces,
    )) == 0
    assert int(root.xpath(
        "count(.//w:body/w:tbl//w:pict)",
        namespaces=namespaces,
    )) == 4
    for pict in root.xpath(".//w:pict", namespaces=namespaces):
        guide_cell = pict.xpath("ancestor::w:tc[1]", namespaces=namespaces)[0]
        assert not guide_cell.xpath(".//w:textDirection", namespaces=namespaces)
    identifiers = re.findall(
        rb'id="epub2a4-guide-(\d+)"',
        _document_xml(output),
    )
    assert len(identifiers) == 4
    assert len(set(identifiers)) == len(identifiers)


def test_page_local_drawingml_guides_use_unique_document_ids(
    tmp_path: Path,
) -> None:
    image_data = BytesIO()
    Image.new("RGB", (20, 20), "white").save(image_data, format="PNG")
    image_blocks = [ImageBlock("Images/pixel.png") for _ in range(9)]
    output = tmp_path / "drawingml-unique-ids.docx"
    write_docx(
        [
            MiniPage(image_blocks, logical_page_number=1),
            MiniPage(image_blocks, logical_page_number=2),
        ],
        output,
        resources={"Images/pixel.png": image_data.getvalue()},
        media_types={"Images/pixel.png": "image/png"},
        settings=LayoutSettings(
            imposition_mode="b6_on_a5",
            output_mark_mode="crop_marks",
            guide_render_mode="drawingml",
            page_numbers=False,
        ),
        imposition_mode="b6_on_a5",
    )

    root = etree.fromstring(_document_xml(output))
    identifiers = root.xpath(
        ".//wp:docPr/@id",
        namespaces={
            "wp": (
                "http://schemas.openxmlformats.org/"
                "drawingml/2006/wordprocessingDrawing"
            ),
        },
    )
    assert len(identifiers) == 22
    assert len(set(identifiers)) == len(identifiers)
