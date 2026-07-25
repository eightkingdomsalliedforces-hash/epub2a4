from __future__ import annotations

from epub_a4_word_desktop.pages.cover_page import TemplatePanel


def test_template_panel_uses_shared_core_template_ids(qtbot) -> None:
    panel = TemplatePanel()
    qtbot.addWidget(panel)
    ids = {str(panel.combo.itemData(index)) for index in range(panel.combo.count())}
    assert ids == {
        "minimal_text",
        "front_image_plain_back",
        "full_spread",
        "top_bottom_blocks",
    }
