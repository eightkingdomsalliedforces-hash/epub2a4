from __future__ import annotations

from PySide6.QtCore import Qt

from epub_a4_word.cover.models import CoverMetadata, CoverProject, ImageMode, TrimSize
from epub_a4_word.cover.project_io import dumps_project
from epub_a4_word_desktop.cover.search_controller import SearchController
from epub_a4_word_desktop.cover.search_panel import CoverSearchPanel


def _project_json(tmp_path) -> str:
    source = tmp_path / "book.epub"
    source.write_bytes(b"placeholder")
    return dumps_project(
        CoverProject(
            schema_version=1,
            source_file=str(source),
            source_type="epub",
            metadata=CoverMetadata(
                title="魔法禁書目錄 01（繁體中文版）",
                author="鎌池和馬",
                language="zh-TW",
            ),
            trim_size=TrimSize(148.0, 210.0),
            page_count=160,
            paper_caliper_mm=0.10,
            manual_spine_width_mm=None,
            bleed_mm=0.0,
            overlap_mm=5.0,
            image_mode=ImageMode.FRONT_ONLY,
            working_dir=str(tmp_path),
        )
    )


def test_free_cover_sources_and_manual_alias_are_visible_by_default(qtbot, tmp_path) -> None:
    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))

    assert panel.google_books_checkbox.isChecked()
    assert panel.open_library_checkbox.isChecked()
    assert panel.gutendex_checkbox.isChecked()
    assert panel.manual_alias_edit.placeholderText() == "原文書名／英文名／其他正式別名（選填）"
    assert panel.search_button.text() == "搜尋封面"
    assert panel.search_button.isEnabled()
    assert panel.configure_credentials_button.text() == "Google Books API 設定"


def test_all_disabled_sources_disable_search_button(qtbot, tmp_path) -> None:
    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))

    panel.google_books_checkbox.setChecked(False)
    panel.open_library_checkbox.setChecked(False)
    panel.gutendex_checkbox.setChecked(False)

    assert not panel.search_button.isEnabled()
    assert "至少啟用一個" in panel.status_label.text()


def test_missing_google_key_does_not_disable_no_key_sources(qtbot, tmp_path) -> None:
    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))

    panel.google_books_checkbox.setChecked(True)
    panel.open_library_checkbox.setChecked(True)
    panel.gutendex_checkbox.setChecked(False)

    assert controller.stored_credential() is None
    assert panel.search_button.isEnabled()


def test_pending_aliases_are_separate_rows_and_accept_restarts_search(
    qtbot, tmp_path, monkeypatch
) -> None:
    from epub_a4_word.cover.search.models import ResolvedAlias, SearchResponse, alias_key

    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))
    alias = ResolvedAlias(
        "A Certain Magical Index",
        "en",
        "wikidata",
        "medium",
        ("書名相符",),
    )
    calls = []
    monkeypatch.setattr(panel, "_search", lambda: calls.append("search"))

    panel._results_ready("public", SearchResponse(pending_aliases=(alias,)))

    assert len(panel.alias_rows) == 1
    panel.alias_rows[0].accepted.emit(alias)
    assert panel.accepted_aliases[alias_key(alias)] == alias
    assert calls == ["search"]


def test_ignoring_pending_alias_removes_only_that_row(qtbot, tmp_path) -> None:
    from epub_a4_word.cover.search.models import ResolvedAlias, SearchResponse, alias_key

    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))
    first = ResolvedAlias("Alias One", "en", "wikidata", "medium")
    second = ResolvedAlias("Alias Two", "ja", "wikidata", "medium")

    panel._results_ready(
        "public",
        SearchResponse(pending_aliases=(first, second)),
    )
    panel.alias_rows[0].ignored.emit(alias_key(first))

    assert alias_key(first) in panel.ignored_alias_keys
    assert [row.alias for row in panel.alias_rows] == [second]


def test_selecting_candidate_has_visible_feedback_and_visible_apply_action(
    qtbot, tmp_path, monkeypatch
) -> None:
    from epub_a4_word.cover.search.models import (
        CandidateCategory,
        SearchCandidate,
        SearchKind,
        SearchResponse,
    )
    from epub_a4_word_desktop.cover.search_panel import CandidateCard

    monkeypatch.setattr(CandidateCard, "_load_preview", lambda self: None)
    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))
    candidate = SearchCandidate(
        provider="open_library",
        candidate_id="OL1W",
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title="魔法禁書目錄",
        author="鎌池和馬",
        isbn="",
        preview_url="https://covers.openlibrary.org/b/id/1-M.jpg",
        image_url="https://covers.openlibrary.org/b/id/1-L.jpg",
        source_page="https://openlibrary.org/works/OL1W",
        media_type="image/jpeg",
    )

    panel._results_ready("public", SearchResponse((candidate,)))
    card = panel.cards[0]
    panel.show()
    qtbot.waitUntil(panel.isVisible)
    qtbot.mouseClick(card.choose_button, Qt.MouseButton.LeftButton)

    assert panel.selected["front"] == candidate
    assert "已選" in card.choose_button.text()
    assert panel.apply_segmented_button.isEnabled()
    assert panel.selection_box.isVisibleTo(panel)
    assert "套用" in panel.apply_segmented_button.text()


def test_search_panel_explains_back_cover_sources(qtbot, tmp_path) -> None:
    controller = SearchController()
    panel = CoverSearchPanel(controller, auto_search=False)
    qtbot.addWidget(panel)
    panel.bind_project(_project_json(tmp_path))

    assert "公開書庫通常只提供正面" in panel.back_cover_help.text()
    assert "EPUB" in panel.back_cover_help.text()
    assert "本機" in panel.back_cover_help.text()
