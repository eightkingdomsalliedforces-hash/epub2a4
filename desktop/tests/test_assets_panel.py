from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

from epub_a4_word.cover.models import CoverMetadata, CoverProject, ImageMode, TrimSize
from epub_a4_word.cover.project_io import dumps_project
from epub_a4_word_desktop.cover.assets_panel import AssetsPanel, import_local_asset
from epub_a4_word_desktop.cover.controller import CoverController


def _make_epub(path: Path, image_bytes: bytes) -> Path:
    container = b'''<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
    opf = b'''<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Book</dc:title></metadata>
  <manifest><item id="cover-image" href="images/cover.png" media-type="image/png" properties="cover-image"/></manifest>
  <spine/>
</package>'''
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/images/cover.png", image_bytes)
    return path


def _project_json(tmp_path: Path, epub_path: Path) -> str:
    return dumps_project(
        CoverProject(
            schema_version=1,
            source_file=str(epub_path),
            source_type="epub",
            metadata=CoverMetadata(
                title="範例書名",
                embedded_images=(
                    {
                        "id": "cover-image",
                        "href": "OEBPS/images/cover.png",
                        "media_type": "image/png",
                        "role": "cover",
                        "width_px": 40,
                        "height_px": 60,
                    },
                ),
            ),
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


def test_local_asset_is_copied_and_deduplicated(tmp_path: Path) -> None:
    source = tmp_path / "來源 圖片.png"
    Image.new("RGB", (40, 60), "white").save(source)
    working = tmp_path / "work"
    first = import_local_asset(source, working)
    second = import_local_asset(source, working)
    assert first == second
    assert first.parent == (working / "assets").resolve()
    assert first.is_file()
    assert first != source


def test_embedded_cover_selection_extracts_to_working_dir(qtbot, tmp_path: Path) -> None:
    source_png = tmp_path / "source.png"
    Image.new("RGB", (40, 60), "white").save(source_png)
    epub_path = _make_epub(tmp_path / "book.epub", source_png.read_bytes())
    controller = CoverController(working_dir=tmp_path / "work", auto_preview=False)
    controller.replace_project(_project_json(tmp_path / "work", epub_path), clear_history=True)
    panel = AssetsPanel(controller)
    qtbot.addWidget(panel)
    panel.refresh_from_project(controller.project_json)
    with qtbot.waitSignal(panel.asset_selected) as signal:
        panel.select_embedded_asset("cover-image")
    selected = Path(signal.args[0])
    assert selected.parent == (controller.working_dir / "assets").resolve()
    assert selected.is_file()


def test_invalid_local_image_is_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "broken.png"
    invalid.write_bytes(b"not an image")
    try:
        import_local_asset(invalid, tmp_path / "work")
    except ValueError as exc:
        assert "圖片" in str(exc)
    else:
        raise AssertionError("invalid image was accepted")
