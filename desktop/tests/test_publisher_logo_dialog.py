from __future__ import annotations

from epub_a4_word.cover.publisher_directory import publisher_profile
from epub_a4_word.cover.search.logo_models import (
    LogoCandidate,
    LogoSearchPage,
    LogoSourceCategory,
)
from epub_a4_word_desktop.cover.publisher_logo_dialog import PublisherLogoDialog


class FakeSearch:
    def search(self, query, *, profile, page_token=None, limit=20):
        suffix = "2" if page_token else "1"
        return LogoSearchPage(
            candidates=(
                LogoCandidate(
                    provider="fake",
                    candidate_id=f"candidate-{suffix}",
                    title=f"台灣角川 Logo {suffix}",
                    image_url=f"https://example.test/logo-{suffix}.png",
                    preview_url="",
                    source_page="https://www.kadokawa.com.tw/",
                    source_category=LogoSourceCategory.OFFICIAL,
                    source_domain="kadokawa.com.tw",
                    media_type="image/png",
                    official_source=True,
                ),
            ),
            next_page_token="next" if not page_token else None,
        )


def test_candidate_dialog_does_not_auto_select_first_result(qtbot) -> None:
    dialog = PublisherLogoDialog(search_service=FakeSearch(), auto_start=False)
    qtbot.addWidget(dialog)

    dialog.start_search("台灣角川", publisher_profile("台灣角川"), synchronous=True)

    assert dialog.results.count() == 1
    assert dialog.selected_candidate() is None
    assert not dialog.choose_button.isEnabled()
    assert "官方來源" in dialog.results.item(0).text()


def test_candidate_dialog_selects_explicit_candidate_and_loads_more(qtbot) -> None:
    dialog = PublisherLogoDialog(search_service=FakeSearch(), auto_start=False)
    qtbot.addWidget(dialog)
    dialog.start_search("台灣角川", publisher_profile("台灣角川"), synchronous=True)

    dialog.results.setCurrentRow(0)
    assert dialog.selected_candidate().candidate_id == "candidate-1"
    assert dialog.choose_button.isEnabled()

    dialog.load_more(synchronous=True)
    assert dialog.results.count() == 2
