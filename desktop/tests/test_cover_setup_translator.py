from __future__ import annotations

from pathlib import Path

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
