from __future__ import annotations

from epub_a4_word.cover.search.errors import SearchQuotaError
from epub_a4_word_desktop.cover.search_controller import _message_for
from epub_a4_word_desktop.cover.setup_panel import CoverSetupPanel
from epub_a4_word_desktop.pages.cover_page import TemplatePanel


def _combo_values(combo) -> list[str]:
    return [str(combo.itemData(index)) for index in range(combo.count())]


def test_desktop_template_options_remain_available(qtbot) -> None:
    setup = CoverSetupPanel()
    toolbar = TemplatePanel()
    qtbot.addWidget(setup)
    qtbot.addWidget(toolbar)

    expected = [
        "minimal",
        "top_bottom_blocks",
        "full_bleed_image",
        "classic_book",
        "publisher_back_matter",
        "modern_vertical_back_with_spine",
    ]
    assert _combo_values(setup.template_combo) == expected
    assert _combo_values(toolbar.combo) == expected


def test_rate_limit_message_does_not_claim_daily_quota_is_exhausted() -> None:
    message = _message_for(
        SearchQuotaError(
            "搜尋服務暫時限制請求（HTTP 429），可能是短期限流，不一定代表每日額度已用完。"
        )
    )

    assert "暫時限制" in message
    assert "不一定代表每日額度已用完" in message
