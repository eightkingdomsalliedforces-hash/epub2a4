from __future__ import annotations

from pathlib import Path

from epub_a4_word.cover.models import (
    CoverMetadata,
    CoverProject,
    ImageMode,
    TrimSize,
)
from epub_a4_word.cover.project_io import dumps_project
from epub_a4_word_desktop.cover import export_worker as export_worker_module
from epub_a4_word_desktop.cover.export_worker import ExportWorker, run_export


def _project_json(tmp_path: Path) -> str:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return dumps_project(
        CoverProject(
            schema_version=1,
            source_file=str(source),
            source_type="epub",
            metadata=CoverMetadata(title="範例書", author="作者"),
            trim_size=TrimSize(105.0, 148.0),
            page_count=160,
            paper_caliper_mm=0.10,
            manual_spine_width_mm=None,
            bleed_mm=3.0,
            overlap_mm=5.0,
            image_mode=ImageMode.FRONT_ONLY,
            working_dir=str(tmp_path),
        )
    )


def test_export_creates_independent_named_files(tmp_path: Path) -> None:
    result = run_export(_project_json(tmp_path), tmp_path / "exports", dpi=200)
    pdf = Path(result["pdf"]["path"])
    docx = Path(result["docx"]["path"])
    assert pdf.name == "範例書_完整書封.pdf"
    assert docx.name == "範例書_完整書封.docx"
    assert pdf.is_file()
    assert docx.is_file()


def test_worker_emits_ordered_progress_and_completion(qtbot, tmp_path: Path) -> None:
    worker = ExportWorker(
        _project_json(tmp_path),
        tmp_path / "範例書_完整書封.pdf",
        tmp_path / "範例書_完整書封.docx",
        200,
    )
    stages: list[str] = []
    completed: list[dict] = []
    worker.signals.progress.connect(stages.append)
    worker.signals.completed.connect(completed.append)
    worker.run()
    assert stages == ["準備", "輸出 PDF", "輸出 DOCX", "完成"]
    assert completed


def test_failed_export_preserves_existing_outputs(monkeypatch, qtbot, tmp_path: Path) -> None:
    pdf = tmp_path / "existing.pdf"
    docx = tmp_path / "existing.docx"
    pdf.write_bytes(b"old pdf")
    docx.write_bytes(b"old docx")

    def fail_export(project_json: str, pdf_path: str, docx_path: str, dpi: int):
        Path(pdf_path).write_bytes(b"partial new pdf")
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(export_worker_module.shared_service, "export_cover", fail_export)
    worker = ExportWorker(_project_json(tmp_path), pdf, docx, 200)
    errors: list[str] = []
    worker.signals.failed.connect(errors.append)
    worker.run()
    assert errors == ["simulated failure"]
    assert pdf.read_bytes() == b"old pdf"
    assert docx.read_bytes() == b"old docx"
