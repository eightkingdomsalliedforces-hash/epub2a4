from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable
from zipfile import ZipFile

from docx import Document
from lxml import etree
from PIL import Image
import pytest

from epub_a4_word.cover.docx_export import export_docx
from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
)
from epub_a4_word.cover.templates import apply_template


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v": "urn:schemas-microsoft-com:vml",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _project_with_image(
    sample_project: Callable[..., CoverProject],
    tmp_path: Path,
    *,
    trim: tuple[float, float],
) -> CoverProject:
    base = apply_template(sample_project(trim=trim), "minimal_text")
    image_path = tmp_path / "cover-background.png"
    Image.new("RGB", (1200, 900), (210, 220, 230)).save(image_path)
    image = CoverElement(
        id="editable-background",
        kind=ElementKind.IMAGE,
        region=Region.SPREAD,
        transform=ElementTransform(0.0, 0.0, 400.0, 220.0),
        z_index=-10,
        content={"path": str(image_path), "fit": "cover"},
    )
    return replace(
        base,
        image_mode=ImageMode.FULL_SPREAD,
        elements=(image, *base.elements),
    )


def _document_xml(path: Path) -> etree._Element:
    with ZipFile(path) as package:
        return etree.fromstring(package.read("word/document.xml"))


def test_docx_has_editable_text_picture_and_line_objects(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(105.0, 148.0))
    result = export_docx(project, tmp_path / "cover.docx")
    document = _document_xml(result.path)

    assert result.page_count == 1
    assert result.mode == "single"
    assert document.xpath("count(.//wp:anchor)", namespaces=NS) >= 1
    assert document.xpath("count(.//w:txbxContent)", namespaces=NS) >= 3
    assert document.xpath("count(.//v:line)", namespaces=NS) >= 1
    assert "範例書名" in "".join(document.xpath(".//w:t/text()", namespaces=NS))


def test_split_docx_has_two_exact_a4_sections(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(148.0, 210.0))
    path = export_docx(project, tmp_path / "split.docx").path
    document = _document_xml(path)
    sections = document.xpath(".//w:sectPr", namespaces=NS)

    assert len(sections) == 2
    for section in sections:
        size = section.find("w:pgSz", namespaces=NS)
        margins = section.find("w:pgMar", namespaces=NS)
        assert size is not None
        assert margins is not None
        width = int(size.get(f"{{{NS['w']}}}w"))
        height = int(size.get(f"{{{NS['w']}}}h"))
        assert sorted((width, height)) == pytest.approx(sorted((11906, 16838)), abs=1)
        for name in ("top", "right", "bottom", "left", "header", "footer", "gutter"):
            assert margins.get(f"{{{NS['w']}}}{name}") == "0"


def test_split_image_is_anchored_once_per_page_with_crop(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(148.0, 210.0))
    path = export_docx(project, tmp_path / "split-crop.docx").path
    document = _document_xml(path)

    anchors = document.xpath(".//wp:anchor", namespaces=NS)
    crops = document.xpath(".//a:srcRect", namespaces=NS)
    assert len(anchors) >= 2
    assert len(crops) >= 2
    assert any(
        any(int(crop.get(name, "0")) > 0 for name in ("l", "t", "r", "b"))
        for crop in crops
    )


def test_text_boxes_contain_real_word_text_and_absolute_vml_positioning(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(105.0, 148.0))
    path = export_docx(project, tmp_path / "editable.docx").path
    document = _document_xml(path)

    shapes = document.xpath(".//v:shape[v:textbox]", namespaces=NS)
    assert shapes
    assert all("position:absolute" in shape.get("style", "") for shape in shapes)
    assert document.xpath(".//w:txbxContent//w:t[text()='範例書名']", namespaces=NS)


def test_docx_package_reopens_and_has_image_relationships(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(105.0, 148.0))
    path = export_docx(project, tmp_path / "valid.docx").path

    reopened = Document(path)
    assert len(reopened.sections) == 1
    with ZipFile(path) as package:
        names = set(package.namelist())
        relationships = etree.fromstring(package.read("word/_rels/document.xml.rels"))
    assert "word/document.xml" in names
    assert any(name.startswith("word/media/") for name in names)
    assert relationships.xpath(
        "count(.//*[contains(@Type, '/image')])"
    ) >= 1


def test_docx_has_no_trailing_manual_page_break(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(148.0, 210.0))
    path = export_docx(project, tmp_path / "no-trailing-break.docx").path
    document = _document_xml(path)
    body = document.find("w:body", namespaces=NS)
    assert body is not None
    last_paragraph = body.xpath("./w:p[last()]", namespaces=NS)
    if last_paragraph:
        assert not last_paragraph[0].xpath(
            ".//w:br[@w:type='page']", namespaces=NS
        )


def test_split_docx_uses_same_readable_page_marks_without_spine_page(
    sample_project: Callable[..., CoverProject], tmp_path: Path
) -> None:
    project = _project_with_image(sample_project, tmp_path, trim=(148.0, 210.0))
    path = export_docx(project, tmp_path / "readable-marks.docx").path
    document = _document_xml(path)
    text = "\n".join(document.xpath(".//w:t/text()", namespaces=NS))

    assert "第 1 頁／2：封底側" in text
    assert "第 2 頁／2：正面側" in text
    assert "100% 實際大小列印，請關閉「符合紙張大小」" in text
    assert "重疊黏貼區" in text
    assert "← 5 mm 拼接重疊區 →" not in text
    assert "書脊" not in text
    assert len(document.xpath(".//w:sectPr", namespaces=NS)) == 2
