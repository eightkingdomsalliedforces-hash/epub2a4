from __future__ import annotations

from pathlib import Path

import pytest

from epub_a4_word_desktop.cover.publisher_metadata_panel import (
    PublisherMetadataPanel,
    PublisherMetadataValues,
)
from epub_a4_word_desktop.cover.setup_panel import CoverSetupPanel


def test_publisher_metadata_panel_normalizes_all_fields(qtbot) -> None:
    panel = PublisherMetadataPanel()
    qtbot.addWidget(panel)
    panel.isbn_edit.setText("978-4-04-867179-8")
    panel.isbn_addon_edit.setText(" 12345 ")
    panel.publisher_edit.setText("  台灣角川  ")
    panel.price_edit.setText("  NT$110/HK$35 ")
    panel.publication_place_edit.setText("  香港代理：角川洲立出版  ")
    panel.translator_edit.setText("  李彥樺  ")
    panel.english_title_edit.setText(" A Certain Magical Index ")
    panel.volume_number_edit.setText(" 1 ")
    panel.arc_label_edit.setText(" 舊約 ")
    panel.series_name_edit.setText(" 電擊文庫 ")
    panel.internal_book_code_edit.setText(" CL0308-17 ")
    panel.spine_accent_color_edit.setText(" #F15A24 ")

    values = panel.values()

    assert values == PublisherMetadataValues(
        isbn="9784048671798",
        isbn_addon="12345",
        publisher="台灣角川",
        price="NT$110/HK$35",
        publication_place="香港代理：角川洲立出版",
        translator="李彥樺",
        publisher_id="",
        english_title="A Certain Magical Index",
        volume_number="1",
        arc_label="舊約",
        series_name="電擊文庫",
        internal_book_code="CL0308-17",
        spine_accent_color="#F15A24",
    )


def test_publisher_metadata_panel_rejects_invalid_addon(qtbot) -> None:
    panel = PublisherMetadataPanel()
    qtbot.addWidget(panel)
    panel.isbn_addon_edit.setText("123")

    with pytest.raises(ValueError, match="附加碼"):
        panel.values()


def test_cover_setup_uses_shared_publisher_panel_and_passes_settings(qtbot, tmp_path: Path) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    panel.set_source(tmp_path / "book.epub", page_count=160, confirmed=True)
    panel.publisher_metadata_panel.publisher_edit.setText("台灣角川")
    panel.publisher_metadata_panel.english_title_edit.setText("Index")
    panel.publisher_metadata_panel.volume_number_edit.setText("1")

    values = panel.values()
    settings = values.settings(tmp_path)

    assert isinstance(panel.publisher_metadata_panel, PublisherMetadataPanel)
    assert panel.translator_edit is panel.publisher_metadata_panel.translator_edit
    assert settings["publisher"] == "台灣角川"
    assert settings["english_title"] == "Index"
    assert settings["volume_number"] == "1"
