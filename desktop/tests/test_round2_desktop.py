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


def test_bleed_defaults_to_zero_and_explains_it_is_not_image_creation(qtbot) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)

    assert panel.bleed_spin.value() == 0.0
    assert "與圖片產生無關" in panel.bleed_spin.toolTip()


def test_public_google_books_search_reuses_saved_google_api_key() -> None:
    http = CaptureHttp()
    facade = SharedSearchFacade(http)

    facade.search_public(
        {"title": "測試書", "author": "作者", "isbn": "", "language": "zh-TW"},
        ProviderCredential("BOOKS_API_KEY", "SEARCH_ENGINE_ID"),
    )

    google_call = next(call for call in http.calls if "googleapis.com/books" in call[0])
    assert google_call[1]["key"] == "BOOKS_API_KEY"


def test_source_inspection_reports_embedded_front_and_back_cover_status(qtbot) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)

    panel.load_inspection(
        {
            "source_path": "book.epub",
            "page_count": 120,
            "page_count_estimated": True,
            "metadata": {
                "embedded_images": [
                    {"role": "front_cover"},
                    {"role": "back_cover"},
                ]
            },
        }
    )

    assert panel.cover_status_note.text() == "已找到正面封面；已找到封底"


def test_source_inspection_marks_medium_back_cover_as_needing_confirmation(qtbot) -> None:
    panel = CoverSetupPanel()
    qtbot.addWidget(panel)

    panel.load_inspection(
        {
            "source_path": "book.epub",
            "page_count": 120,
            "metadata": {
                "embedded_images": [
                    {"id": "front-image", "role": "front_cover"},
                    {"id": "back-image", "role": "back_cover_candidate"},
                ]
            },
        }
    )

    assert panel.cover_status_note.text() == "已找到正面封面；可能的封底需確認"
    assert panel.confirm_back_cover.isVisibleTo(panel)
    assert not panel.confirm_back_cover.isChecked()

    panel.confirm_back_cover.setChecked(True)

    values = panel.values()
    assert values.confirmed_back_cover_asset_id == "back-image"
    assert values.settings(Path("work"))["confirmed_back_cover_asset_id"] == "back-image"


def test_google_books_credential_dialog_requires_only_api_key(qtbot) -> None:
    from epub_a4_word_desktop.cover.credential_dialog import CredentialDialog

    dialog = CredentialDialog(ProviderCredential("BOOKS_KEY", "LEGACY_CX"))
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Google Books API 設定"
    assert not hasattr(dialog, "search_engine_id")
    assert dialog._value() == ProviderCredential("BOOKS_KEY")
