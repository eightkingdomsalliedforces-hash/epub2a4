#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = ROOT / "python/src"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from lxml import etree
from pypdf import PdfReader

from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import CoverProject
from epub_a4_word.cover.print_plan import build_print_plan
from epub_a4_word.cover.project_io import loads_project


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
}
TWIPS_PER_MM = 1440 / 25.4


def _configure_utf8_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="strict")


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def project_geometry_snapshot(project: CoverProject) -> dict[str, Any]:
    layout = calculate_layout(project)
    plan = build_print_plan(layout)
    spine = layout.spine_rect
    modern_spine_elements = []
    for element in project.elements:
        if not element.id.startswith("modern-spine-"):
            continue
        transform = element.transform
        inside_spine = (
            spine.x_mm <= transform.x_mm
            and transform.x_mm + transform.width_mm <= spine.right_mm + 1e-9
            and spine.y_mm <= transform.y_mm
            and transform.y_mm + transform.height_mm <= spine.bottom_mm + 1e-9
        )
        modern_spine_elements.append(
            {
                "id": element.id,
                "layout_role": element.content.get("layout_role", ""),
                "x_mm": transform.x_mm,
                "y_mm": transform.y_mm,
                "width_mm": transform.width_mm,
                "height_mm": transform.height_mm,
                "inside_spine": inside_spine,
            }
        )
    return {
        "schema_version": project.schema_version,
        "trim_width_mm": project.trim_size.width_mm,
        "trim_height_mm": project.trim_size.height_mm,
        "page_count": project.page_count,
        "paper_caliper_mm": project.paper_caliper_mm,
        "manual_spine_width_mm": project.manual_spine_width_mm,
        "bleed_mm": project.bleed_mm,
        "overlap_mm": project.overlap_mm,
        "layout": _jsonable(asdict(layout)),
        "print_plan": _jsonable(asdict(plan)),
        "modern_spine_elements": modern_spine_elements,
    }


def _modern_spine_errors(geometry: dict[str, Any]) -> list[str]:
    elements = geometry["modern_spine_elements"]
    errors = [
        f"{item['id']} exceeds the physical spine"
        for item in elements
        if not item["inside_spine"]
    ]
    publisher_count = sum(
        item["layout_role"] == "publisher" for item in elements
    )
    if publisher_count > 1:
        errors.append(
            f"modern spine contains {publisher_count} publisher elements"
        )
    return errors


def inspect_pdf(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    reader = PdfReader(source)
    media_boxes = []
    for index, page in enumerate(reader.pages, start=1):
        width_pt = float(page.mediabox.width)
        height_pt = float(page.mediabox.height)
        media_boxes.append(
            {
                "page": index,
                "width_pt": width_pt,
                "height_pt": height_pt,
                "width_mm": width_pt / 72.0 * 25.4,
                "height_mm": height_pt / 72.0 * 25.4,
            }
        )
    return {
        "path": str(source.resolve()),
        "file_size_bytes": source.stat().st_size,
        "page_count": len(reader.pages),
        "media_boxes": media_boxes,
    }


def inspect_docx(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    with ZipFile(source) as package:
        document = etree.fromstring(package.read("word/document.xml"))
    sections = []
    for index, section in enumerate(document.xpath(".//w:sectPr", namespaces=NS), start=1):
        page_size = section.find("w:pgSz", namespaces=NS)
        if page_size is None:
            sections.append({"section": index, "width_twips": None, "height_twips": None})
            continue
        width_twips = int(page_size.get(f"{{{NS['w']}}}w"))
        height_twips = int(page_size.get(f"{{{NS['w']}}}h"))
        sections.append(
            {
                "section": index,
                "orientation": page_size.get(f"{{{NS['w']}}}orient", "portrait"),
                "width_twips": width_twips,
                "height_twips": height_twips,
                "width_mm": width_twips / TWIPS_PER_MM,
                "height_mm": height_twips / TWIPS_PER_MM,
            }
        )
    return {
        "path": str(source.resolve()),
        "file_size_bytes": source.stat().st_size,
        "section_count": len(sections),
        "sections": sections,
        "anchored_picture_count": int(
            document.xpath("count(.//wp:anchor)", namespaces=NS)
        ),
        "text_box_count": int(
            document.xpath("count(.//w:txbxContent)", namespaces=NS)
        ),
        "line_shape_count": int(document.xpath("count(.//v:line)", namespaces=NS)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect cover project geometry plus PDF and DOCX export structure."
    )
    parser.add_argument("project_json", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--geometry-output", type=Path)
    args = parser.parse_args(argv)

    project = loads_project(args.project_json.read_text("utf-8"))
    geometry = project_geometry_snapshot(project)
    if args.geometry_output is not None:
        args.geometry_output.parent.mkdir(parents=True, exist_ok=True)
        args.geometry_output.write_text(
            json.dumps(geometry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            "utf-8",
        )
    result = {
        "geometry": geometry,
        "pdf": inspect_pdf(args.pdf),
        "docx": inspect_docx(args.docx),
    }
    errors = _modern_spine_errors(geometry)
    if errors:
        result["errors"] = errors
    _configure_utf8_stdout()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
