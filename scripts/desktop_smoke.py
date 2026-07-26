#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = ROOT / "python/src"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))


def _fixture_project(output_dir: Path) -> str:
    from epub_a4_word.cover.models import (
        CoverMetadata,
        CoverProject,
        ImageMode,
        TrimSize,
    )
    from epub_a4_word.cover.project_io import dumps_project
    from epub_a4_word.cover.templates import apply_template

    source = output_dir / "desktop-smoke.epub"
    source.write_bytes(b"desktop smoke fixture")
    project = CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="桌面煙霧測試", author="epub2a4"),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(output_dir),
    )
    return dumps_project(apply_template(project, "minimal_text"))


def run_smoke(output_dir: Path | str) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from epub_a4_word.cover import service as cover_service
    from epub_a4_word_desktop.cover.export_worker import run_export
    from epub_a4_word_desktop.main_window import AppRoute, MainWindow

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication(["epub2a4-desktop-smoke"])
    window = MainWindow()
    window.show()
    application.processEvents()

    window.navigate(AppRoute.CONVERTER)
    application.processEvents()
    window.navigate(AppRoute.COVER)
    application.processEvents()

    project_json = _fixture_project(destination)
    cover_page = window.pages[AppRoute.COVER]
    cover_page.controller.auto_preview = False
    cover_page.controller.replace_project(project_json, clear_history=True)
    preview_path = destination / "desktop-smoke-preview.png"
    preview = cover_service.render_preview(
        project_json,
        str(preview_path),
        max_px=900,
    )
    cover_page.canvas.set_preview(preview["path"])
    application.processEvents()

    export = run_export(project_json, destination / "exports", dpi=200)
    result = {
        "route": window.current_route.value,
        "preview_path": str(Path(preview["path"]).resolve()),
        "original_pdf_path": str(Path(export["original_pdf"]["path"]).resolve()),
        "print_pdf_path": str(Path(export["print_pdf"]["path"]).resolve()),
        "print_docx_path": str(Path(export["print_docx"]["path"]).resolve()),
    }
    window.close()
    application.processEvents()
    return result


def _verify_result(result: dict[str, Any]) -> None:
    if result.get("route") != "cover":
        raise RuntimeError(f"desktop smoke wrong route: {result.get('route')}")
    for key in (
        "preview_path",
        "original_pdf_path",
        "print_pdf_path",
        "print_docx_path",
    ):
        if not Path(str(result[key])).is_file():
            raise RuntimeError(f"desktop smoke missing {key}: {result[key]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PySide6 desktop smoke gate.")
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    if args.output_dir is not None:
        result = run_smoke(args.output_dir)
        _verify_result(result)
    else:
        with tempfile.TemporaryDirectory(prefix="epub2a4-desktop-smoke-") as value:
            result = run_smoke(Path(value))
            _verify_result(result)
    print("desktop smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
