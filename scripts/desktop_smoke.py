from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path
import tempfile
import time
from typing import Any, Sequence


def _smoke_project(root: Path) -> str:
    from PIL import Image

    from epub_a4_word.cover.geometry import calculate_layout
    from epub_a4_word.cover.models import (
        CoverElement,
        CoverMetadata,
        CoverProject,
        ElementKind,
        ElementTransform,
        ImageMode,
        Region,
        TrimSize,
    )
    from epub_a4_word.cover.project_io import dumps_project

    working_dir = root / "working"
    assets_dir = working_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    image_path = assets_dir / "smoke-cover.png"
    Image.new("RGB", (400, 600), "white").save(image_path)

    base = CoverProject(
        schema_version=1,
        source_file=str(root / "smoke.epub"),
        source_type="epub",
        metadata=CoverMetadata(title="桌面煙霧測試", author="epub2a4"),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(working_dir),
        background={"color": "#ffffff"},
    )
    front = calculate_layout(base).front_rect
    project = replace(
        base,
        elements=(
            CoverElement(
                id="smoke-front-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(
                    front.x_mm,
                    front.y_mm,
                    front.width_mm,
                    front.height_mm,
                ),
                z_index=0,
                content={"path": str(image_path), "fit": "cover"},
            ),
        ),
    )
    return dumps_project(project)


def run_smoke(output_root: Path | str | None = None) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from epub_a4_word_desktop.cover.export_worker import run_export
    from epub_a4_word_desktop.main_window import AppRoute, MainWindow

    root = (
        Path(output_root).expanduser().resolve()
        if output_root is not None
        else Path(tempfile.mkdtemp(prefix="epub2a4-desktop-smoke-"))
    )
    root.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(["epub2a4-desktop-smoke"])

    window = MainWindow()
    preview_paths: list[Path] = []
    try:
        window.navigate(AppRoute.COVER)
        page = window.pages[AppRoute.COVER]
        page.controller.working_dir = (root / "working").resolve()
        page.controller.working_dir.mkdir(parents=True, exist_ok=True)
        project_json = _smoke_project(root)
        page.controller.preview_ready.connect(lambda path: preview_paths.append(Path(path)))
        page.controller.replace_project(project_json, clear_history=True)
        page.controller.schedule_preview()

        deadline = time.monotonic() + 20.0
        while not preview_paths and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        if not preview_paths or not preview_paths[-1].is_file():
            raise RuntimeError("桌面封面預覽逾時。")

        exported = run_export(project_json, root / "exports", dpi=200)
        pdf_path = Path(str(exported["pdf"]["path"])).resolve()
        docx_path = Path(str(exported["docx"]["path"])).resolve()
        if not pdf_path.is_file() or not docx_path.is_file():
            raise RuntimeError("桌面封面匯出未產生完整檔案。")

        return {
            "route": window.current_route.value,
            "preview_path": str(preview_paths[-1].resolve()),
            "pdf_path": str(pdf_path),
            "docx_path": str(docx_path),
        }
    finally:
        window.close()
        app.processEvents()
        if owns_app:
            app.quit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the complete PySide6 desktop smoke gate.")
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = run_smoke(args.output_dir)
    print("desktop smoke: PASS")
    print(f"preview: {result['preview_path']}")
    print(f"pdf: {result['pdf_path']}")
    print(f"docx: {result['docx_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
