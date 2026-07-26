from __future__ import annotations

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
