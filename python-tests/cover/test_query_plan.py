from __future__ import annotations

from epub_a4_word.cover.search.models import ResolvedAlias
from epub_a4_word.cover.search.query_plan import (
    build_query_plan,
    normalize_book_identity,
)


def test_normalizes_translated_edition_label_and_trailing_volume() -> None:
    identity = normalize_book_identity(
        title="魔法禁書目錄 ０１（繁體中文版）.epub",
        author="  鎌池 和馬  ",
        isbn="urn:isbn:978-4-8402-2658-5",
        language="zh-TW",
    )

    assert identity.original_title == "魔法禁書目錄 ０１（繁體中文版）.epub"
    assert identity.normalized_title == "魔法禁書目錄"
    assert identity.author == "鎌池 和馬"
    assert identity.normalized_author == "鎌池 和馬"
    assert identity.volume == "1"
    assert identity.isbn == "9784840226585"
    assert identity.language == "zh-TW"


def test_extracts_vol_and_roman_numeral_volume_formats() -> None:
    vol = normalize_book_identity(title="Example Series Vol. 2", author="A")
    roman = normalize_book_identity(title="Example Series Volume IV", author="A")

    assert (vol.normalized_title, vol.volume) == ("Example Series", "2")
    assert (roman.normalized_title, roman.volume) == ("Example Series", "4")


def test_uuid_and_invalid_isbn_are_not_treated_as_isbn() -> None:
    uuid_identity = normalize_book_identity(
        title="Book",
        isbn="550e8400-e29b-41d4-a716-446655440000",
    )
    invalid_identity = normalize_book_identity(title="Book", isbn="9780000000001")

    assert uuid_identity.isbn == ""
    assert invalid_identity.isbn == ""


def test_query_plan_priority_is_isbn_manual_original_normalized_then_aliases() -> None:
    identity = normalize_book_identity(
        title="魔法禁書目錄 01（繁體中文版）",
        author="鎌池和馬",
        isbn="978-4-8402-2658-5",
        language="zh-TW",
    )
    aliases = (
        ResolvedAlias(
            value="とある魔術の禁書目録",
            language="ja",
            source="wikidata",
            confidence="high",
            reasons=("same author",),
        ),
        ResolvedAlias(
            value="A Certain Magical Index",
            language="en",
            source="wikidata",
            confidence="high",
            reasons=("same work",),
        ),
    )

    plan = build_query_plan(
        identity,
        manual_alias="とある魔術の禁書目録 第1巻",
        aliases=aliases,
    )

    assert [(item.kind, item.value, item.source) for item in plan.items] == [
        ("isbn", "9784840226585", "epub"),
        ("title", "とある魔術の禁書目録 第1巻", "user"),
        ("title", "魔法禁書目錄 01（繁體中文版）", "epub"),
        ("title", "魔法禁書目錄", "normalized"),
        ("title", "とある魔術の禁書目録", "wikidata"),
        ("title", "A Certain Magical Index", "wikidata"),
    ]
    assert all(item.author == "鎌池和馬" for item in plan.items)


def test_query_plan_deduplicates_normalized_equivalent_titles() -> None:
    identity = normalize_book_identity(title="Example 01", author="Author")
    plan = build_query_plan(
        identity,
        manual_alias=" example 01 ",
        aliases=(
            ResolvedAlias(
                value="EXAMPLE 01",
                language="en",
                source="local_cache",
                confidence="high",
                reasons=(),
            ),
        ),
    )

    title_items = [item for item in plan.items if item.kind == "title"]
    assert [item.value for item in title_items] == ["example 01", "Example"]


def test_medium_alias_does_not_enter_plan_until_accepted() -> None:
    identity = normalize_book_identity(title="魔法禁書目錄", author="鎌池和馬")
    alias = ResolvedAlias(
        "A Certain Magical Index", "en", "wikidata", "medium"
    )

    initial = build_query_plan(identity, aliases=(alias,))
    accepted = build_query_plan(
        identity,
        aliases=(alias,),
        accepted_aliases=(alias,),
    )

    assert "A Certain Magical Index" not in [item.value for item in initial.items]
    accepted_item = next(
        item for item in accepted.items if item.value == "A Certain Magical Index"
    )
    assert accepted_item.confidence == "high"
    assert accepted_item.reason == "user-confirmed alias"
