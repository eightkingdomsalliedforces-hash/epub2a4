from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from .models import BookIdentity, ResolvedAlias
from .query_plan import normalize_book_identity, normalize_isbn

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_USER_AGENT = (
    "EPUB2A4-CoverTool/0.8 "
    "(+https://github.com/eightkingdomsalliedforces-hash/epub2a4)"
)
_MEDIA_INSTANCE_IDS = frozenset(
    {
        "Q11424",     # film
        "Q7889",      # video game
        "Q5398426",   # television series
        "Q581714",    # animated series
        "Q63952888",  # anime television series
    }
)


@dataclass(frozen=True)
class AliasResolution:
    aliases: tuple[ResolvedAlias, ...]
    isbns: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def _snak_value(claim: object) -> object | None:
    if not isinstance(claim, dict):
        return None
    mainsnak = claim.get("mainsnak")
    if not isinstance(mainsnak, dict):
        return None
    datavalue = mainsnak.get("datavalue")
    if not isinstance(datavalue, dict):
        return None
    return datavalue.get("value")


def _claim_values(entity: dict[str, Any], property_id: str) -> tuple[object, ...]:
    claims = entity.get("claims")
    if not isinstance(claims, dict):
        return ()
    raw = claims.get(property_id)
    if not isinstance(raw, list):
        return ()
    return tuple(value for item in raw if (value := _snak_value(item)) is not None)


def _entity_ids(entity: dict[str, Any], property_id: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in _claim_values(entity, property_id):
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            result.append(str(value["id"]))
    return tuple(dict.fromkeys(result))


def _named_values(entity: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    labels = entity.get("labels")
    if isinstance(labels, dict):
        for language, raw in labels.items():
            if isinstance(raw, dict) and str(raw.get("value", "")).strip():
                result.append((str(raw.get("language") or language), str(raw["value"]).strip()))
    aliases = entity.get("aliases")
    if isinstance(aliases, dict):
        for language, raw_values in aliases.items():
            if not isinstance(raw_values, list):
                continue
            for raw in raw_values:
                if isinstance(raw, dict) and str(raw.get("value", "")).strip():
                    result.append((str(raw.get("language") or language), str(raw["value"]).strip()))
    for value in _claim_values(entity, "P1476"):
        if isinstance(value, dict) and str(value.get("text", "")).strip():
            result.append((str(value.get("language") or ""), str(value["text"]).strip()))
    unique: dict[tuple[str, str], tuple[str, str]] = {}
    for language, value in result:
        unique.setdefault((language.casefold(), _text_key(value)), (language, value))
    return tuple(unique.values())


def _description_text(entity: dict[str, Any]) -> str:
    descriptions = entity.get("descriptions")
    if not isinstance(descriptions, dict):
        return ""
    return " ".join(
        str(raw.get("value", ""))
        for raw in descriptions.values()
        if isinstance(raw, dict)
    )


def _text_key(value: str) -> str:
    identity = normalize_book_identity(title=value)
    text = unicodedata.normalize("NFKC", identity.normalized_title).casefold()
    return "".join(char for char in text if char.isalnum())


def _person_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(char for char in text if char.isalnum())


def _ordinal(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    match = re.search(r"\d+", text)
    if match:
        return str(int(match.group()))
    roman = text.upper()
    if not re.fullmatch(r"[IVXLCDM]+", roman):
        return ""
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for character in reversed(roman):
        current = values[character]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return str(total) if total > 0 else ""


def _entity_volumes(entity: dict[str, Any]) -> tuple[str, ...]:
    values = list(_claim_values(entity, "P1545"))
    claims = entity.get("claims")
    series_claims = claims.get("P179", []) if isinstance(claims, dict) else []
    if isinstance(series_claims, list):
        for claim in series_claims:
            qualifiers = claim.get("qualifiers") if isinstance(claim, dict) else None
            ordinals = qualifiers.get("P1545", []) if isinstance(qualifiers, dict) else []
            if isinstance(ordinals, list):
                values.extend(
                    value
                    for item in ordinals
                    if (value := _snak_value({"mainsnak": item})) is not None
                )
    normalized = [_ordinal(value) for value in values]
    return tuple(dict.fromkeys(value for value in normalized if value))


def _entity_isbns(entity: dict[str, Any]) -> tuple[str, ...]:
    values = (*_claim_values(entity, "P212"), *_claim_values(entity, "P957"))
    normalized = [normalize_isbn(str(value)) for value in values]
    return tuple(dict.fromkeys(value for value in normalized if value))


def _is_non_book_media(entity: dict[str, Any]) -> bool:
    return bool(set(_entity_ids(entity, "P31")) & _MEDIA_INSTANCE_IDS)


class WikidataAliasResolver:
    def __init__(self, http) -> None:
        self.http = http

    def resolve(
        self,
        identity: BookIdentity,
        *,
        max_entities: int = 8,
    ) -> AliasResolution:
        try:
            return self._resolve(identity, max_entities=max_entities)
        except Exception as exc:
            return AliasResolution((), (), (f"Wikidata：{exc}",))

    def _resolve(self, identity: BookIdentity, *, max_entities: int) -> AliasResolution:
        search_text = identity.normalized_title or identity.original_title
        if not search_text.strip():
            return AliasResolution((), ())
        language = (identity.language or "zh-TW").replace("_", "-").casefold()
        search_payload = self.http.get_json(
            WIKIDATA_API_URL,
            {
                "action": "wbsearchentities",
                "search": search_text,
                "language": language,
                "uselang": language,
                "type": "item",
                "limit": max(1, min(int(max_entities), 20)),
                "format": "json",
                "formatversion": 2,
            },
            headers={"User-Agent": WIKIDATA_USER_AGENT, "Accept": "application/json"},
        )
        search_results = search_payload.get("search")
        if not isinstance(search_results, list):
            return AliasResolution((), ())
        candidate_ids = tuple(
            dict.fromkeys(
                str(item.get("id"))
                for item in search_results
                if isinstance(item, dict) and re.fullmatch(r"Q\d+", str(item.get("id", "")))
            )
        )
        if not candidate_ids:
            return AliasResolution((), ())

        candidates = self._get_entities(candidate_ids, language)
        related_ids = tuple(
            dict.fromkeys(
                related_id
                for entity in candidates.values()
                for property_id in ("P50", "P179")
                for related_id in _entity_ids(entity, property_id)
            )
        )
        related = self._get_entities(related_ids, language) if related_ids else {}

        aliases: list[ResolvedAlias] = []
        isbns: list[str] = []
        seen_aliases: set[tuple[str, str]] = set()
        identity_title_keys = {
            _text_key(identity.original_title),
            _text_key(identity.normalized_title),
        }
        identity_author_key = _person_key(identity.author)

        for candidate_id in candidate_ids:
            entity = candidates.get(candidate_id)
            if entity is None or _is_non_book_media(entity):
                continue
            names = _named_values(entity)
            title_match = any(_text_key(value) in identity_title_keys for _, value in names)
            entity_isbns = _entity_isbns(entity)
            isbn_match = bool(identity.isbn and identity.isbn in entity_isbns)
            if not title_match and not isbn_match:
                continue

            reasons: list[str] = ["書名相符" if title_match else "ISBN 相符"]
            confidence = "high"
            author_ids = _entity_ids(entity, "P50")
            author_names = [
                value
                for author_id in author_ids
                for _, value in _named_values(related.get(author_id, {}))
            ]
            if identity_author_key and author_names:
                author_match = any(_person_key(value) == identity_author_key for value in author_names)
                if author_match:
                    reasons.append("作者相符")
                else:
                    confidence = "medium"
                    reasons.append("作者不符，需確認")
            elif identity_author_key and identity_author_key in _person_key(_description_text(entity)):
                reasons.append("描述中的作者相符")

            volumes = _entity_volumes(entity)
            if identity.volume and volumes:
                if identity.volume in volumes:
                    reasons.append("卷數相符")
                else:
                    confidence = "medium"
                    reasons.append("卷數不符，需確認")

            if confidence == "high":
                isbns.extend(entity_isbns)
            for alias_language, alias_value in names:
                alias_key = _text_key(alias_value)
                if not alias_key or alias_key in identity_title_keys:
                    continue
                dedupe_key = (alias_language.casefold(), alias_key)
                if dedupe_key in seen_aliases:
                    continue
                seen_aliases.add(dedupe_key)
                aliases.append(
                    ResolvedAlias(
                        value=alias_value,
                        language=alias_language or None,
                        source="wikidata",
                        confidence=confidence,
                        reasons=tuple(reasons),
                    )
                )
        return AliasResolution(
            aliases=tuple(aliases),
            isbns=tuple(dict.fromkeys(isbns)),
        )

    def _get_entities(
        self,
        entity_ids: tuple[str, ...],
        language: str,
    ) -> dict[str, dict[str, Any]]:
        if not entity_ids:
            return {}
        languages = tuple(dict.fromkeys((language, "zh-tw", "zh-hant", "zh", "ja", "en")))
        payload = self.http.get_json(
            WIKIDATA_API_URL,
            {
                "action": "wbgetentities",
                "ids": "|".join(entity_ids),
                "props": "labels|aliases|descriptions|claims",
                "languages": "|".join(languages),
                "languagefallback": 1,
                "format": "json",
                "formatversion": 2,
            },
            headers={"User-Agent": WIKIDATA_USER_AGENT, "Accept": "application/json"},
        )
        entities = payload.get("entities")
        if not isinstance(entities, dict):
            return {}
        return {
            str(entity_id): entity
            for entity_id, entity in entities.items()
            if isinstance(entity, dict) and not entity.get("missing")
        }
