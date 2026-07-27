from __future__ import annotations

from epub_a4_word.pagination import LayoutSettings
from epub_a4_word_desktop.conversion.layout_preview import LayoutPreview


def test_b6_preview_uses_shared_bottom_right_placement_and_full_crop_lines(qtbot) -> None:
    preview = LayoutPreview()
    qtbot.addWidget(preview)

    preview.set_settings(
        LayoutSettings(
            imposition_mode="b6_on_a5",
            cut_guides=True,
            output_mark_mode="crop_marks",
        )
    )

    placement = preview.placement
    assert (
        placement.paper_width_mm,
        placement.paper_height_mm,
        placement.content_x_mm,
        placement.content_y_mm,
        placement.content_width_mm,
        placement.content_height_mm,
    ) == (148.0, 210.0, 20.0, 28.0, 128.0, 182.0)
    assert placement.guides == (
        type(placement.guides[0])(0.0, 28.0, 148.0, 28.0, "crop"),
        type(placement.guides[1])(20.0, 0.0, 20.0, 210.0, "crop"),
    )
    assert preview.finished_edge_message == ""


def test_single_a5_preview_reports_finished_paper_edge_and_no_internal_guides(qtbot) -> None:
    preview = LayoutPreview()
    qtbot.addWidget(preview)

    preview.set_settings(
        LayoutSettings(
            imposition_mode="single_a5",
            cut_guides=True,
        )
    )

    assert preview.placement.guides == ()
    assert preview.finished_edge_message == "紙張邊緣即成品邊"
    assert "紙張邊緣即成品邊" in preview.toolTip()
