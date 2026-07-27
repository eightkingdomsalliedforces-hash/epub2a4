from __future__ import annotations

from PySide6.QtWidgets import QLabel

from epub_a4_word_desktop.cover.publisher_metadata_panel import PublisherMetadataPanel


def test_invalid_isbn_addon_shows_error_beside_addon_field(qtbot) -> None:
    panel = PublisherMetadataPanel()
    qtbot.addWidget(panel)
    panel.show()

    panel.isbn_addon_edit.setText("123")

    field_error = panel.findChild(
        QLabel,
        "publisher-metadata-error-isbn_addon",
    )
    assert field_error is not None
    assert field_error.isVisible()
    assert "附加碼" in field_error.text()
    assert not panel.error_label.isVisible()


def test_correcting_field_clears_only_its_validation_error(qtbot) -> None:
    panel = PublisherMetadataPanel()
    qtbot.addWidget(panel)
    panel.show()

    panel.spine_accent_color_edit.setText("orange")
    color_error = panel.findChild(
        QLabel,
        "publisher-metadata-error-spine_accent_color",
    )
    assert color_error is not None
    assert color_error.isVisible()

    panel.spine_accent_color_edit.setText("#F15A24")

    assert not color_error.isVisible()
    assert color_error.text() == ""
