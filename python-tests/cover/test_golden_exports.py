from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from lxml import etree
from PIL import Image
import pytest

from epub_a4_word.cover.docx_export import export_docx
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.pdf_export import export_pdf
from epub_a4_word.cover.print_plan import build_print_plan
from epub_a4_word.cover.project_io import dumps_project, loads_project
from scripts.compare_cover_geometry import collect_mm_values, compare
from scripts.inspect_cover_exports import (
    inspect_docx,
    inspect_pdf,
    project_geometry_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_JSON = ROOT / "python-tests/fixtures/cover/golden-project.json"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


@pytest.fixture
def golden_project(tmp_path: Path):
    image_path = tmp_path / "golden-background.png"
    Image.new("RGB", (2400, 1800), (225, 225, 225)).save(image_path)
    payload = json.loads(GOLDEN_JSON.read_text("utf-8"))
    payload["source_file"] = str(tmp_path / "body.epub")
    payload["working_dir"] = str(tmp_path)
    for element in payload["elements"]:
        if element["kind"] == "image":
            element["content"]["path"] = str(image_path)
    return loads_project(json.dumps(payload, ensure_ascii=False))


def test_golden_project_has_frozen_physical_values(golden_project) -> None:
    assert golden_project.schema_version == 1
    assert golden_project.trim_size.width_mm == 148.0
    assert golden_project.trim_size.height_mm == 210.0
    assert golden_project.page_count == 160
    assert golden_project.paper_caliper_mm == 0.1
    assert golden_project.manual_spine_width_mm is None
    assert golden_project.bleed_mm == 3.0
    assert golden_project.overlap_mm == 5.0
    assert golden_project.image_mode.value == "full_spread"


def test_golden_pdf_and_docx_structural_acceptance(golden_project, tmp_path: Path) -> None:
    layout = calculate_layout(golden_project)
    print_plan = build_print_plan(layout)
    pdf_result = export_pdf(golden_project, tmp_path / "golden.pdf", dpi=300)
    docx_result = export_docx(golden_project, tmp_path / "golden.docx")

    with ZipFile(docx_result.path) as package:
        document = etree.fromstring(package.read("word/document.xml"))
    docx_anchor_count = int(document.xpath("count(.//wp:anchor)", namespaces=NS))
    docx_text_box_count = int(document.xpath("count(.//w:txbxContent)", namespaces=NS))

    assert layout.spine_width_mm == pytest.approx(8.0)
    assert print_plan.mode == "two_page"
    assert [page.name for page in print_plan.pages] == ["back_side", "front_side"]
    assert pdf_result.page_count == 2
    assert docx_result.page_count == 2
    assert docx_anchor_count >= 2
    assert docx_text_box_count >= 5


def test_geometry_snapshot_is_deterministic_and_contains_mm_values(golden_project) -> None:
    first = project_geometry_snapshot(golden_project)
    second = project_geometry_snapshot(golden_project)
    assert first == second
    assert first["layout"]["spine_width_mm"] == pytest.approx(8.0)
    assert first["print_plan"]["mode"] == "two_page"
    assert len(collect_mm_values(first)) >= 20


def test_export_inspectors_report_pdf_and_docx_structure(golden_project, tmp_path: Path) -> None:
    pdf = export_pdf(golden_project, tmp_path / "inspect.pdf", dpi=300).path
    docx = export_docx(golden_project, tmp_path / "inspect.docx").path
    pdf_info = inspect_pdf(pdf)
    docx_info = inspect_docx(docx)
    assert pdf_info["page_count"] == 2
    assert len(pdf_info["media_boxes"]) == 2
    assert pdf_info["file_size_bytes"] > 0
    assert docx_info["section_count"] == 2
    assert docx_info["anchored_picture_count"] >= 2
    assert docx_info["text_box_count"] >= 5
    assert docx_info["file_size_bytes"] > 0


def test_compare_geometry_reports_tolerance(capsys) -> None:
    left = collect_mm_values({"layout": {"spine_width_mm": 8.0}})
    right = collect_mm_values({"layout": {"spine_width_mm": 8.03}})
    assert compare(left, right, 0.05) == 0
    assert "maximum delta=0.030000 mm" in capsys.readouterr().out
    assert compare(left, right, 0.01) == 1


def test_inspection_and_geometry_cli_tools(golden_project, tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    project_path.write_text(dumps_project(golden_project), "utf-8")
    pdf = export_pdf(golden_project, tmp_path / "cli.pdf", dpi=200).path
    docx = export_docx(golden_project, tmp_path / "cli.docx").path
    snapshot_path = tmp_path / "snapshot.json"

    inspect_run = subprocess.run(
        [
            sys.executable,
            "scripts/inspect_cover_exports.py",
            str(project_path),
            str(pdf),
            str(docx),
            "--geometry-output",
            str(snapshot_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert inspect_run.returncode == 0, inspect_run.stderr
    payload = json.loads(inspect_run.stdout)
    assert payload["pdf"]["page_count"] == 2
    assert payload["docx"]["section_count"] == 2
    assert snapshot_path.is_file()

    compare_run = subprocess.run(
        [
            sys.executable,
            "scripts/compare_cover_geometry.py",
            str(snapshot_path),
            str(snapshot_path),
            "--tolerance-mm",
            "0.001",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert compare_run.returncode == 0, compare_run.stderr
    assert "maximum delta=0.000000 mm" in compare_run.stdout


def test_schema_and_status_documentation_are_present() -> None:
    schema = (ROOT / "docs/cover-project-schema-v1.md").read_text("utf-8")
    readme = (ROOT / "README.md").read_text("utf-8")
    status = (ROOT / "BUILD_STATUS.md").read_text("utf-8")
    assert "schema_version" in schema
    assert "working_dir" in schema
    assert "back | spine | front" in schema
    assert "免費封面搜尋" in readme
    assert "Windows 可攜版" in readme
    assert "Windows portable EXE" in status
    assert "Android 實體裝置" in status
