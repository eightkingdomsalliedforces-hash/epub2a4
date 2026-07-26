from __future__ import annotations

from epub_a4_word.cover.search.query_plan import normalize_book_identity
from epub_a4_word.cover.search.wikidata import WikidataAliasResolver


def _claim(value, *, qualifiers=None):
    claim = {"mainsnak": {"datavalue": {"value": value}}}
    if qualifiers is not None:
        claim["qualifiers"] = qualifiers
    return claim


def _entity_claim(entity_id: str):
    return _claim({"entity-type": "item", "id": entity_id})


def _string_claim(value: str):
    return _claim(value)


class FakeHttp:
    def __init__(self, entities, *, search=None, error: Exception | None = None) -> None:
        self.entities = entities
        self.search = search or [{"id": "Q100", "label": "魔法禁書目錄"}]
        self.error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url, params, headers=None):
        self.calls.append((url, dict(params)))
        if self.error is not None:
            raise self.error
        if params["action"] == "wbsearchentities":
            return {"search": self.search}
        ids = str(params["ids"]).split("|")
        return {"entities": {entity_id: self.entities[entity_id] for entity_id in ids}}


def _book_entity(*, instance="Q571", author="Q200", volume="1"):
    return {
        "id": "Q100",
        "labels": {
            "zh-tw": {"language": "zh-tw", "value": "魔法禁書目錄"},
            "ja": {"language": "ja", "value": "とある魔術の禁書目録"},
            "en": {"language": "en", "value": "A Certain Magical Index"},
        },
        "aliases": {
            "ja": [{"language": "ja", "value": "禁書目録"}],
        },
        "descriptions": {
            "zh-tw": {"language": "zh-tw", "value": "鎌池和馬創作的輕小說"},
        },
        "claims": {
            "P31": [_entity_claim(instance)],
            "P50": [_entity_claim(author)],
            "P1476": [
                _claim({"text": "とある魔術の禁書目録", "language": "ja"})
            ],
            "P212": [_string_claim("978-4-8402-2658-5")],
            "P1545": [_string_claim(volume)],
        },
    }


def _person(entity_id="Q200", name="鎌池和馬"):
    return {
        "id": entity_id,
        "labels": {
            "zh-tw": {"language": "zh-tw", "value": name},
            "ja": {"language": "ja", "value": name},
        },
        "aliases": {},
        "descriptions": {},
        "claims": {},
    }


def test_resolves_chinese_title_to_japanese_english_aliases_and_isbn() -> None:
    http = FakeHttp({"Q100": _book_entity(), "Q200": _person()})
    resolver = WikidataAliasResolver(http)
    identity = normalize_book_identity(
        title="魔法禁書目錄 01（繁體中文版）",
        author="鎌池和馬",
        language="zh-TW",
    )

    result = resolver.resolve(identity)

    aliases = {(item.value, item.language, item.confidence) for item in result.aliases}
    assert ("とある魔術の禁書目録", "ja", "high") in aliases
    assert ("A Certain Magical Index", "en", "high") in aliases
    assert result.isbns == ("9784840226585",)
    assert result.warnings == ()
    assert [call[1]["action"] for call in http.calls] == [
        "wbsearchentities",
        "wbgetentities",
        "wbgetentities",
    ]


def test_rejects_same_name_film_or_game_entity() -> None:
    http = FakeHttp({"Q100": _book_entity(instance="Q11424"), "Q200": _person()})
    identity = normalize_book_identity(title="魔法禁書目錄", author="鎌池和馬")

    result = WikidataAliasResolver(http).resolve(identity)

    assert result.aliases == ()
    assert result.isbns == ()


def test_author_mismatch_downgrades_aliases_to_medium() -> None:
    http = FakeHttp({"Q100": _book_entity(), "Q200": _person(name="另一位作者")})
    identity = normalize_book_identity(title="魔法禁書目錄 01", author="鎌池和馬")

    result = WikidataAliasResolver(http).resolve(identity)

    assert result.aliases
    assert {item.confidence for item in result.aliases} == {"medium"}
    assert any("作者不符" in reason for item in result.aliases for reason in item.reasons)


def test_wrong_volume_downgrades_aliases_to_medium() -> None:
    http = FakeHttp({"Q100": _book_entity(volume="3"), "Q200": _person()})
    identity = normalize_book_identity(title="魔法禁書目錄 02", author="鎌池和馬")

    result = WikidataAliasResolver(http).resolve(identity)

    assert result.aliases
    assert {item.confidence for item in result.aliases} == {"medium"}
    assert any("卷數不符" in reason for item in result.aliases for reason in item.reasons)


def test_network_failure_becomes_warning_instead_of_exception() -> None:
    http = FakeHttp({}, error=RuntimeError("offline"))
    identity = normalize_book_identity(title="魔法禁書目錄", author="鎌池和馬")

    result = WikidataAliasResolver(http).resolve(identity)

    assert result.aliases == ()
    assert result.isbns == ()
    assert result.warnings == ("Wikidata：offline",)
