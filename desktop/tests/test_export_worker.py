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
from epub_a4_word_desktop.cover.export_worker import (
    ExportWorker,
    export_paths,
    run_export,
)


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


def test_export_paths_have_clear_three_file_names(tmp_path: Path) -> None:
    paths = export_paths(_project_json(tmp_path), tmp_path / "exports")

    assert paths.original_pdf.name == "範例書-完整書衣-原始尺寸.pdf"
    assert paths.print_pdf.name == "範例書-A4拼接列印.pdf"
    assert paths.print_docx.name == "範例書-A4拼接列印.docx"


def test_export_creates_three_independent_named_files(tmp_path: Path) -> None:
    result = run_export(_project_json(tmp_path), tmp_path / "exports", dpi=200)
    original = Path(result["original_pdf"]["path"])
    print_pdf = Path(result["print_pdf"]["path"])
    print_docx = Path(result["print_docx"]["path"])

    assert original.name == "範例書-完整書衣-原始尺寸.pdf"
    assert print_pdf.name == "範例書-A4拼接列印.pdf"
    assert print_docx.name == "範例書-A4拼接列印.docx"
    assert original.is_file()
    assert print_pdf.is_file()
    assert print_docx.is_file()


def test_worker_emits_ordered_progress_and_completion(qtbot, tmp_path: Path) -> None:
    paths = export_paths(_project_json(tmp_path), tmp_path)
    worker = ExportWorker(_project_json(tmp_path), paths, 200)
    stages: list[str] = []
    completed: list[dict] = []
    worker.signals.progress.connect(stages.append)
    worker.signals.completed.connect(completed.append)
    worker.run()

    assert stages == [
        "準備",
        "輸出完整尺寸 PDF",
        "輸出 A4 PDF",
        "輸出 A4 DOCX",
        "完成",
    ]
    assert completed


def test_failed_export_preserves_existing_outputs(monkeypatch, qtbot, tmp_path: Path) -> None:
    paths = export_paths(_project_json(tmp_path), tmp_path)
    paths.original_pdf.write_bytes(b"old original")
    paths.print_pdf.write_bytes(b"old print pdf")
    paths.print_docx.write_bytes(b"old print docx")

    def fail_export(
        project_json: str,
        original_pdf_path: str,
        print_pdf_path: str,
        print_docx_path: str,
        dpi: int,
    ):
        Path(original_pdf_path).write_bytes(b"partial original")
        Path(print_pdf_path).write_bytes(b"partial print")
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(
        export_worker_module.shared_service,
        "export_cover_bundle",
        fail_export,
    )
    worker = ExportWorker(_project_json(tmp_path), paths, 200)
    errors: list[str] = []
    worker.signals.failed.connect(errors.append)
    worker.run()

    assert errors == ["simulated failure"]
    assert paths.original_pdf.read_bytes() == b"old original"
    assert paths.print_pdf.read_bytes() == b"old print pdf"
    assert paths.print_docx.read_bytes() == b"old print docx"


def test_third_replacement_failure_restores_all_previous_files(
    monkeypatch, tmp_path: Path
) -> None:
    paths = export_paths(_project_json(tmp_path), tmp_path)
    paths.original_pdf.write_bytes(b"old original")
    paths.print_pdf.write_bytes(b"old print pdf")
    paths.print_docx.write_bytes(b"old print docx")
    real_replace = export_worker_module.os.replace
    target_replacements = 0

    def fail_third(source, destination):
        nonlocal target_replacements
        destination_path = Path(destination)
        if destination_path in {
            paths.original_pdf,
            paths.print_pdf,
            paths.print_docx,
        }:
            target_replacements += 1
            if target_replacements == 3:
                raise OSError("third replacement failed")
        return real_replace(source, destination)

    monkeypatch.setattr(export_worker_module.os, "replace", fail_third)

    try:
        run_export(_project_json(tmp_path), tmp_path, dpi=200)
    except OSError as exc:
        assert "third replacement" in str(exc)
    else:
        raise AssertionError("third replacement failure must propagate")

    assert paths.original_pdf.read_bytes() == b"old original"
    assert paths.print_pdf.read_bytes() == b"old print pdf"
    assert paths.print_docx.read_bytes() == b"old print docx"
