from __future__ import annotations

import copy
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Callable
from zipfile import BadZipFile, ZipFile

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from pypdf import PdfReader

from epub_a4_word.cover import service as shared_service
from epub_a4_word.cover.project_io import loads_project


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ExportPaths:
    original_pdf: Path
    print_pdf: Path
    print_docx: Path

    def all(self) -> tuple[Path, Path, Path]:
        return (self.original_pdf, self.print_pdf, self.print_docx)


def _safe_title(value: str, fallback: str = "封面") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    cleaned = cleaned.strip().rstrip(". ")
    return cleaned or fallback


def export_paths(project_json: str, output_dir: Path | str) -> ExportPaths:
    project = loads_project(project_json)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    fallback = Path(project.source_file).stem or "封面"
    base = _safe_title(project.metadata.title, _safe_title(fallback))
    return ExportPaths(
        original_pdf=output / f"{base}-完整書衣-原始尺寸.pdf",
        print_pdf=output / f"{base}-A4拼接列印.pdf",
        print_docx=output / f"{base}-A4拼接列印.docx",
    )


def _validate_pdf(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"PDF 匯出檔案不存在：{path}")
    reader = PdfReader(path)
    if not reader.pages:
        raise ValueError("PDF 沒有頁面。")


def _validate_docx(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"DOCX 匯出檔案不存在：{path}")
    try:
        with ZipFile(path) as package:
            names = set(package.namelist())
    except BadZipFile as exc:
        raise ValueError("DOCX 不是有效的 ZIP 套件。") from exc
    required = {
        "[Content_Types].xml",
        "word/document.xml",
        "word/_rels/document.xml.rels",
    }
    missing = required - names
    if missing:
        raise ValueError("DOCX 缺少必要部件：" + "、".join(sorted(missing)))


def _final_result(result: dict[str, Any], paths: ExportPaths) -> dict[str, Any]:
    final = copy.deepcopy(result)
    final.setdefault("original_pdf", {})["path"] = str(paths.original_pdf)
    final.setdefault("print_pdf", {})["path"] = str(paths.print_pdf)
    final.setdefault("print_docx", {})["path"] = str(paths.print_docx)
    return final


def _replace_outputs(
    temporary: ExportPaths,
    targets: ExportPaths,
    work: Path,
) -> None:
    for target in targets.all():
        target.parent.mkdir(parents=True, exist_ok=True)

    backups: dict[Path, Path] = {}
    for index, target in enumerate(targets.all(), start=1):
        if target.exists():
            backup = work / f"previous-{index}{target.suffix}"
            shutil.copy2(target, backup)
            backups[target] = backup

    try:
        for source, target in zip(temporary.all(), targets.all(), strict=True):
            os.replace(source, target)
    except Exception:
        for target in targets.all():
            backup = backups.get(target)
            if backup is not None and backup.exists():
                os.replace(backup, target)
            elif backup is None:
                target.unlink(missing_ok=True)
        raise


def _export_transaction(
    project_json: str,
    paths: ExportPaths,
    dpi: int,
    progress: ProgressCallback,
) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="epub2a4-export-"))
    temporary = ExportPaths(
        original_pdf=work / paths.original_pdf.name,
        print_pdf=work / paths.print_pdf.name,
        print_docx=work / paths.print_docx.name,
    )
    try:
        progress("準備")
        progress("輸出完整尺寸 PDF")
        result = shared_service.export_cover_bundle(
            project_json,
            str(temporary.original_pdf),
            str(temporary.print_pdf),
            str(temporary.print_docx),
            dpi,
        )
        _validate_pdf(temporary.original_pdf)
        progress("輸出 A4 PDF")
        _validate_pdf(temporary.print_pdf)
        progress("輸出 A4 DOCX")
        _validate_docx(temporary.print_docx)
        _replace_outputs(temporary, paths, work)
        progress("完成")
        return _final_result(result, paths)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_export(
    project_json: str,
    output_dir: Path | str,
    *,
    dpi: int = 300,
) -> dict[str, Any]:
    paths = export_paths(project_json, output_dir)
    return _export_transaction(
        project_json,
        paths,
        dpi,
        lambda _stage: None,
    )


class ExportSignals(QObject):
    progress = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)


class ExportWorker(QRunnable):
    def __init__(
        self,
        project_json: str,
        paths: ExportPaths,
        dpi: int,
    ) -> None:
        super().__init__()
        self.project_json = project_json
        self.paths = ExportPaths(
            paths.original_pdf.expanduser().resolve(),
            paths.print_pdf.expanduser().resolve(),
            paths.print_docx.expanduser().resolve(),
        )
        self.dpi = int(dpi)
        self.signals = ExportSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = _export_transaction(
                self.project_json,
                self.paths,
                self.dpi,
                self.signals.progress.emit,
            )
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.completed.emit(result)
