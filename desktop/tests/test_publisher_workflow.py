from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

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
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word.cover.search.models import CandidateCategory, SearchCandidate, SearchKind
from epub_a4_word.cover.templates import apply_template
from epub_a4_word_desktop.cover.canvas import CoverCanvas
from epub_a4_word_desktop.cover.controller import CoverController
from epub_a4_word_desktop.cover.inspector import ElementInspector
from epub_a4_word_desktop.cover.items import CoverBarcodeItem
from epub_a4_word_desktop.cover.search_panel import CandidateCard
from epub_a4_word_desktop.pages.cover_page import publisher_logo_search_url


def _project(tmp_path: Path) -> CoverProject:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    return CoverProject(
        schema_version=1,
        source_file=str(source),
        source_type="epub",
        metadata=CoverMetadata(title="Example Volume 1", publisher="Publisher"),
        trim_size=TrimSize(105.0, 148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        working_dir=str(tmp_path),
    )


def _image_element(tmp_path: Path) -> CoverElement:
    image = tmp_path / "image.png"
    QPixmap(100, 100).save(str(image))
    return CoverElement(
        id="image",
        kind=ElementKind.IMAGE,
        region=Region.FRONT,
        transform=ElementTransform(0.0, 0.0, 50.0, 50.0),
        content={"path": str(image), "fit": "cover", "scale": 0.75},
    )


def _publisher_project(tmp_path: Path, isbn: str = "9780306406157") -> CoverProject:
    project = _project(tmp_path)
    return apply_template(
        replace(project, metadata=replace(project.metadata, isbn=isbn)),
        "publisher_back_matter",
    )


def test_controller_apply_isbn_updates_metadata_and_template_barcode(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    project = apply_template(_project(tmp_path), "publisher_back_matter")
    controller.replace_project(dumps_project(project), clear_history=True)

    controller.apply_isbn("978-0-306-40615-7")

    updated = loads_project(controller.project_json)
    assert updated.metadata.isbn == "9780306406157"
    assert updated.elements_by_id["back-isbn-code"].content["isbn"] == "9780306406157"
    assert updated.elements_by_id["back-isbn-label"].content["text"] == "ISBN-13 9780306406157"


def test_controller_assign_publisher_logo_replaces_existing_logo(qtbot, tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    QPixmap(12, 12).save(str(first))
    QPixmap(16, 16).save(str(second))
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    controller.replace_project(dumps_project(_publisher_project(tmp_path)), clear_history=True)

    controller.assign_publisher_logo(first)
    controller.assign_publisher_logo(second)

    logos = [item for item in loads_project(controller.project_json).elements if item.id == "back-publisher-logo"]
    assert len(logos) == 1
    assert Path(str(logos[0].content["path"])).is_file()


def test_controller_converts_isbn10_to_ean13_for_barcode(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    project = apply_template(_project(tmp_path), "publisher_back_matter")
    controller.replace_project(dumps_project(project), clear_history=True)

    controller.apply_isbn("0-306-40615-2")

    updated = loads_project(controller.project_json)
    assert updated.metadata.isbn == "9780306406157"
    assert updated.elements_by_id["back-isbn-code"].content["isbn"] == "9780306406157"


def test_controller_isbn_sync_preserves_moved_barcode_geometry(tmp_path: Path) -> None:
    project = _publisher_project(tmp_path)
    barcode = project.elements_by_id["back-isbn-code"]
    moved_transform = ElementTransform(9.0, 11.0, 63.0, 28.0)
    project = replace(
        project,
        elements=tuple(
            replace(element, transform=moved_transform)
            if element.id == barcode.id
            else element
            for element in project.elements
        ),
    )
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    controller.replace_project(dumps_project(project), clear_history=True)

    controller.apply_isbn("9783161484100")

    updated = loads_project(controller.project_json)
    assert updated.elements_by_id["back-isbn-code"].transform == moved_transform
    assert updated.elements_by_id["back-isbn-code"].content["isbn"] == "9783161484100"


def test_canvas_creates_interactive_barcode_item(qtbot, tmp_path: Path) -> None:
    canvas = CoverCanvas()
    qtbot.addWidget(canvas)
    project = _publisher_project(tmp_path)

    canvas.set_project(dumps_project(project))

    assert isinstance(canvas.items_by_id["back-isbn-code"], CoverBarcodeItem)
    canvas.select_element("back-isbn-code")
    assert canvas.items_by_id["back-isbn-code"].isSelected()


def test_inspector_exposes_scale_slider_and_transform_shortcuts(qtbot, tmp_path: Path) -> None:
    inspector = ElementInspector()
    qtbot.addWidget(inspector)
    inspector.set_element(_image_element(tmp_path))

    assert inspector.scale_slider.minimum() == 10
    assert inspector.scale_slider.maximum() == 500
    assert inspector.scale_slider.value() == 75

    with qtbot.waitSignal(inspector.patch_requested) as fit_signal:
        qtbot.mouseClick(inspector.fit_button, Qt.MouseButton.LeftButton)
    assert fit_signal.args == [
        "image",
        {"content": {"fit": "contain", "scale": 1.0, "offset_x": 0.0, "offset_y": 0.0}},
    ]

    with qtbot.waitSignal(inspector.patch_requested) as center_signal:
        qtbot.mouseClick(inspector.center_button, Qt.MouseButton.LeftButton)
    assert center_signal.args == ["image", {"content": {"offset_x": 0.0, "offset_y": 0.0}}]


def test_candidate_card_displays_all_valid_isbns(qtbot) -> None:
    from PySide6.QtNetwork import QNetworkAccessManager

    candidate = SearchCandidate(
        provider="google_books",
        candidate_id="book",
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title="Example Volume 1",
        author="Author",
        isbn="9780306406157",
        isbns=("0306406152", "9780306406157"),
        preview_url="https://example.test/preview.jpg",
        image_url="https://example.test/image.jpg",
        source_page="https://example.test/book",
    )
    card = CandidateCard(candidate, QNetworkAccessManager())
    qtbot.addWidget(card)

    assert "ISBN-10 0306406152" in card.isbn_label.text()
    assert "ISBN-13 9780306406157" in card.isbn_label.text()


def test_publisher_logo_search_uses_wikimedia_media_search() -> None:
    url = publisher_logo_search_url("台灣角川")
    assert url.startswith("https://commons.wikimedia.org/w/index.php?")
    assert "search=%E5%8F%B0%E7%81%A3%E8%A7%92%E5%B7%9D+logo" in url
