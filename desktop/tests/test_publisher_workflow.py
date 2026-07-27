from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager

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
from epub_a4_word_desktop.cover.search_panel import CandidateCard, candidate_isbn_summary


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


def _candidate(*, isbns: tuple[str, ...] = ("0306406152", "9780306406157")) -> SearchCandidate:
    return SearchCandidate(
        provider="google_books",
        candidate_id="book",
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title="Example Volume 1",
        author="Author",
        isbn="9780306406157",
        isbns=isbns,
        publisher="Publisher",
        language="zh-TW",
        classification_reasons=("書名與卷數相符",),
        preview_url="https://example.test/preview.jpg",
        image_url="https://example.test/image.jpg",
        source_page="https://example.test/book",
    )


def test_controller_apply_isbn_updates_metadata_and_template_barcode(tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    project = apply_template(_project(tmp_path), "publisher_back_matter")
    controller.replace_project(dumps_project(project), clear_history=True)

    controller.apply_isbn("978-0-306-40615-7")

    updated = loads_project(controller.project_json)
    assert updated.metadata.isbn == "9780306406157"
    assert updated.elements_by_id["back-isbn-code"].content["isbn"] == "9780306406157"
    assert updated.elements_by_id["back-isbn-label"].content["text"] == "ISBN 978-030-640-615-7"


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


def test_publisher_logo_image_uses_contain_without_cropping(qtbot, tmp_path: Path) -> None:
    controller = CoverController(working_dir=tmp_path, auto_preview=False)
    project = _publisher_project(tmp_path)
    controller.replace_project(dumps_project(project), clear_history=True)
    source = tmp_path / "publisher-logo.png"
    QPixmap(240, 120).save(str(source))

    element_id = controller.add_local_image(source, Region.BACK)

    updated = loads_project(controller.project_json)
    element = updated.elements_by_id[element_id]
    slot = updated.background["publisher_logo_slot"]
    assert element.content["fit"] == "contain"
    assert element.transform.x_mm == slot["x_mm"]
    assert element.transform.y_mm == slot["y_mm"]
    assert element.transform.width_mm == slot["width_mm"]
    assert element.transform.height_mm == slot["height_mm"]


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


def test_candidate_card_explains_recommended_and_corresponding_isbn(qtbot) -> None:
    card = CandidateCard(_candidate(), QNetworkAccessManager())
    qtbot.addWidget(card)

    text = card.isbn_label.text()
    assert "建議 ISBN-13：9780306406157" in text
    assert "對應 ISBN-10：0306406152（同一版本對應碼）" in text
    assert text.count("建議 ISBN-13") == 1
    assert "ISBN-10 0306406152\nISBN-13" not in text
    edition = card.edition_label.text()
    assert "出版社：Publisher" in edition
    assert "語言：zh-TW" in edition
    assert "判定：書名與卷數相符" in edition


def test_unrelated_isbn10_is_not_labelled_as_same_edition() -> None:
    summary = candidate_isbn_summary(_candidate(isbns=("0131103628", "9780306406157")))

    assert summary == "建議 ISBN-13：9780306406157"
    assert "同一版本對應碼" not in summary
