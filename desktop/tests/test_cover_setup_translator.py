from __future__ import annotations

from pathlib import Path

from epub_a4_word_desktop.cover import setup_panel as setup_panel_module
from epub_a4_word_desktop.cover.setup_panel import CoverSetupPanel


def test_setup_values_include_trimmed_translator(qtbot, tmp_path: Path) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    panel.set_source(
        tmp_path / "book.epub",
        page_count=160,
        confirmed=True,
    )
    panel.translator_edit.setText("  李彥樺  ")

    values = panel.values()

    assert values.translator == "李彥樺"
    assert values.settings(tmp_path)["translator"] == "李彥樺"


def test_inspection_uses_description_when_back_copy_is_blank(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"placeholder")
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(
        setup_panel_module,
        "inspect_source",
        lambda *_args: {
            "source_path": str(source),
            "page_count": 120,
            "page_count_estimated": False,
            "metadata": {
                "description": "EPUB 封底簡介",
                "back_vertical_copy": "",
            },
        },
    )

    panel.inspect_source_path(source)

    assert panel.publisher_metadata_panel.back_vertical_copy_edit.toPlainText() == (
        "EPUB 封底簡介"
    )
