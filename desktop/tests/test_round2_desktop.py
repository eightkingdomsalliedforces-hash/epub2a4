from __future__ import annotations

from pathlib import Path

from epub_a4_word.cover.search.models import ProviderCredential
from epub_a4_word_desktop.cover import setup_panel as setup_panel_module
from epub_a4_word_desktop.cover.search_controller import SharedSearchFacade
from epub_a4_word_desktop.cover.setup_panel import CoverSetupPanel


class CaptureHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []

    def get_json(self, url, params, headers=None):
        self.calls.append((url, dict(params), None if headers is None else dict(headers)))
        if "googleapis.com/books" in url:
            return {"items": []}
        return {"docs": []}


def test_browsed_epub_automatically_populates_and_confirms_page_count(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"placeholder")
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)

    monkeypatch.setattr(
        setup_panel_module,
        "inspect_source",
        lambda path, width, height: {
            "source_path": str(path),
            "fixed_page_count": None,
            "page_count": 123,
            "page_count_estimated": True,
            "metadata": {},
        },
    )

    panel.inspect_source_path(source)

    assert panel.page_count_spin.value() == 123
    assert panel.page_count_confirmed.isChecked()
    assert panel.create_button.isEnabled()
    assert "自動估算" in panel.page_count_note.text()


def test_bleed_defaults_to_zero_and_explains_it_does_not_generate_images(qtbot) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)

    assert panel.bleed_spin.value() == 0.0
    assert "不會生成" in panel.bleed_spin.toolTip()


def test_public_google_books_search_reuses_saved_google_api_key() -> None:
    http = CaptureHttp()
    facade = SharedSearchFacade(http)

    facade.search_public(
        {"title": "測試書", "author": "作者", "isbn": "", "language": "zh-TW"},
        ProviderCredential("BOOKS_API_KEY", "SEARCH_ENGINE_ID"),
    )

    google_call = next(call for call in http.calls if "googleapis.com/books" in call[0])
    assert google_call[1]["key"] == "BOOKS_API_KEY"
