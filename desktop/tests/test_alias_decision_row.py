from PySide6.QtCore import Qt

from epub_a4_word.cover.search.models import ResolvedAlias, alias_key
from epub_a4_word_desktop.cover.alias_decision_row import AliasDecisionRow


def test_alias_row_emits_accept_and_ignore(qtbot) -> None:
    alias = ResolvedAlias(
        "A Certain Magical Index",
        "en",
        "wikidata",
        "medium",
        ("書名相符",),
    )
    row = AliasDecisionRow(alias)
    qtbot.addWidget(row)

    with qtbot.waitSignal(row.accepted) as accepted:
        qtbot.mouseClick(row.accept_button, Qt.MouseButton.LeftButton)
    assert accepted.args == [alias]

    with qtbot.waitSignal(row.ignored) as ignored:
        qtbot.mouseClick(row.ignore_button, Qt.MouseButton.LeftButton)
    assert ignored.args == [alias_key(alias)]


def test_alias_row_displays_value_language_source_and_reasons(qtbot) -> None:
    alias = ResolvedAlias(
        "とある魔術の禁書目録",
        "ja",
        "wikidata",
        "medium",
        ("作者相符", "卷數待確認"),
    )
    row = AliasDecisionRow(alias)
    qtbot.addWidget(row)

    assert row.value_label.text() == "とある魔術の禁書目録"
    assert "ja" in row.detail_label.text()
    assert "wikidata" in row.detail_label.text()
    assert "作者相符" in row.reason_label.text()
    assert "卷數待確認" in row.reason_label.text()
