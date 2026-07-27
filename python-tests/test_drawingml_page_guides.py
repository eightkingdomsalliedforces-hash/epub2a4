from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

from epub_a4_word.docx_writer import write_docx
from epub_a4_word.models import TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, MiniPage


def _page() -> MiniPage:
    return MiniPage(
        [TextBlock((TextRun("正文"),), style="body")],
        used_points=20.0,
        logical_page_number=1,
    )


def _header_xml(path: Path) -> str:
    with ZipFile(path) as archive:
        return "".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith("word/header") and name.endswith(".xml")
        )


def test_b6_drawingml_guides_use_same_full_page_coordinates(tmp_path: Path) -> None:
    output = tmp_path / "drawingml-b6.docx"
    write_docx(
        [_page()],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode="b6_on_a5",
            output_mark_mode="crop_marks",
            cut_guides=True,
            guide_render_mode="drawingml",
        ),
        imposition_mode="b6_on_a5",
    )

    xml = _header_xml(output)
    assert "<w:drawing" in xml
    assert "<v:line" not in xml
    assert xml.count('name="epub2a4-crop-guide-') == 2
    positions = re.findall(
        r'<wp:positionH relativeFrom="page"><wp:posOffset>(\d+)</wp:posOffset></wp:positionH>'
        r'.*?<wp:positionV relativeFrom="page"><wp:posOffset>(\d+)</wp:posOffset></wp:positionV>'
        r'.*?<wp:extent cx="(\d+)" cy="(\d+)"',
        xml,
        flags=re.DOTALL,
    )
    emu_per_mm = 36000
    assert positions == [
        ("0", str(28 * emu_per_mm), str(148 * emu_per_mm), "1"),
        (str(20 * emu_per_mm), "0", "1", str(210 * emu_per_mm)),
    ]


def test_signature_drawingml_fold_guides_are_dashed(tmp_path: Path) -> None:
    output = tmp_path / "drawingml-signature.docx"
    write_docx(
        [_page()],
        output,
        resources={},
        media_types={},
        settings=LayoutSettings(
            imposition_mode="signature16",
            cut_guides=True,
            guide_render_mode="drawingml",
        ),
        imposition_mode="signature16",
    )

    xml = _header_xml(output)
    assert xml.count('name="epub2a4-fold-guide-') == 2
    assert xml.count('<a:prstDash val="dash"') == 2
