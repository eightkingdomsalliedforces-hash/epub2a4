from __future__ import annotations

import copy
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


def _safe_title(value: str, fallback: str = "封面") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    cleaned = cleaned.strip().rstrip(". ")
    return cleaned or fallback


def export_paths(project_json: str, output_dir: Path | str) -> tuple[Path, Path]:
    project = loads_project(project_json)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    fallback = Path(project.source_file).stem or "封面"
    base = _safe_title(project.metadata.title, _safe_title(fallback))
    return (
        output / f"{base}_完整書封.pdf",
        output / f"{base}_完整書封.docx",
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


def _final_result(
    result: dict[str, Any], pdf: Path, docx: Path
) -> dict[str, Any]:
    final = copy.deepcopy(result)
    final.setdefault("pdf", {})["path"] = str(pdf)
    final.setdefault("docx", {})["path"] = str(docx)
    return final


def _replace_outputs(
    temp_pdf: Path,
    temp_docx: Path,
    pdf: Path,
    docx: Path,
    work: Path,
) -> None:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    docx.parent.mkdir(parents=True, exist_ok=True)
    backup_pdf = work / "previous.pdf"
    backup_docx = work / "previous.docx"
    had_pdf = pdf.exists()
    had_docx = docx.exists()
    if had_pdf:
        shutil.copy2(pdf, backup_pdf)
    if had_docx:
        shutil.copy2(docx, backup_docx)
    try:
        os.replace(temp_pdf, pdf)
        os.replace(temp_docx, docx)
    except Exception:
        if had_pdf:
            os.replace(backup_pdf, pdf)
        else:
            pdf.unlink(missing_ok=True)
        if had_docx:
            os.replace(backup_docx, docx)
        else:
            docx.unlink(missing_ok=True)
        raise


def _export_transaction(
    project_json: str,
    pdf: Path,
    docx: Path,
    dpi: int,
    progress: ProgressCallback,
) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="epub2a4-export-"))
    temp_pdf = work / pdf.name
    temp_docx = work / docx.name
    try:
        progress("準備")
        result = shared_service.export_cover(
            project_json,
            str(temp_pdf),
            str(temp_docx),
            dpi,
        )
        progress("輸出 PDF")
        _validate_pdf(temp_pdf)
        progress("輸出 DOCX")
        _validate_docx(temp_docx)
        _replace_outputs(temp_pdf, temp_docx, pdf, docx, work)
        progress("完成")
        return _final_result(result, pdf, docx)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_export(
    project_json: str,
    output_dir: Path | str,
    *,
    dpi: int = 300,
) -> dict[str, Any]:
    pdf, docx = export_paths(project_json, output_dir)
    return _export_transaction(
        project_json,
        pdf,
        docx,
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
        pdf: Path | str,
        docx: Path | str,
        dpi: int,
    ) -> None:
        super().__init__()
        self.project_json = project_json
        self.pdf = Path(pdf).expanduser().resolve()
        self.docx = Path(docx).expanduser().resolve()
        self.dpi = int(dpi)
        self.signals = ExportSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = _export_transaction(
                self.project_json,
                self.pdf,
                self.docx,
                self.dpi,
                self.signals.progress.emit,
            )
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.completed.emit(result)
