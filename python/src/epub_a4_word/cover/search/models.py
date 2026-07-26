from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import re
from urllib.parse import urlsplit

from ..isbn import preferred_isbn, valid_isbns


class SearchKind(StrEnum):
    FRONT = "front"
    BACK = "back"
    SPINE = "spine"
    FULL_SPREAD = "full_spread"
    REFERENCE_PHOTO = "reference_photo"


class CandidateCategory(StrEnum):
    FRONT = "front"
    BACK = "back"
    SPINE = "spine"
    FULL_SPREAD = "full_spread"
    REFERENCE_PHOTO = "reference_photo"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BookIdentity:
    original_title: str
    normalized_title: str
    author: str
    normalized_author: str
    volume: str
    isbn: str
    language: str


@dataclass(frozen=True)
class ResolvedAlias:
    value: str
    language: str | None
    source: str
    confidence: str
    reasons: tuple[str, ...] = ()



def alias_key(alias: ResolvedAlias) -> str:
    return "|".join(
        (
            alias.source.casefold().strip(),
            (alias.language or "").casefold().strip(),
            " ".join(alias.value.casefold().split()),
        )
    )


@dataclass(frozen=True)
class QueryItem:
    kind: str
    value: str
    author: str
    language: str
    confidence: str
    source: str
    reason: str


@dataclass(frozen=True)
class QueryPlan:
    identity: BookIdentity
    items: tuple[QueryItem, ...]


@dataclass(frozen=True)
class CoverSearchRequest:
    kind: SearchKind = SearchKind.FRONT
    query: str = ""
    isbn: str = ""
    title: str = ""
    author: str = ""
    locale: str = "zh-TW"
    max_results: int = 20
    safe_search: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", SearchKind(self.kind))
        if not 1 <= int(self.max_results) <= 40:
            raise ValueError("max_results 必須介於 1 與 40。")
        if not any(str(value).strip() for value in (self.query, self.isbn, self.title)):
            raise ValueError("搜尋至少需要關鍵字、ISBN 或書名。")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "query": self.query,
            "isbn": self.isbn,
            "title": self.title,
            "author": self.author,
            "locale": self.locale,
            "max_results": self.max_results,
            "safe_search": self.safe_search,
        }


@dataclass(frozen=True)
class ProviderCredential:
    api_key: str
    search_engine_id: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.api_key.strip())


@dataclass(frozen=True)
class CandidateClassification:
    category: CandidateCategory
    confidence: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchCandidate:
    provider: str
    candidate_id: str
    query_kind: SearchKind
    proposed_category: CandidateCategory
    title: str
    author: str
    isbn: str
    preview_url: str
    image_url: str
    source_page: str
    isbns: tuple[str, ...] = ()
    language: str = ""
    publisher: str = ""
    width_px: int | None = None
    height_px: int | None = None
    media_type: str = ""
    rights: str = ""
    classification_confidence: float = 0.0
    classification_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_kind", SearchKind(self.query_kind))
        object.__setattr__(self, "proposed_category", CandidateCategory(self.proposed_category))
        source_isbns = valid_isbns(self.isbns)
        fallback_isbns = source_isbns or valid_isbns((self.isbn,))
        object.__setattr__(self, "isbns", source_isbns or fallback_isbns)
        object.__setattr__(self, "isbn", preferred_isbn(fallback_isbns))
        for label, value in (
            ("preview_url", self.preview_url),
            ("image_url", self.image_url),
            ("source_page", self.source_page),
        ):
            if value and urlsplit(value).scheme.casefold() != "https":
                raise ValueError(f"{label} 必須使用 HTTPS。")
        if self.width_px is not None and self.width_px <= 0:
            raise ValueError("width_px 必須大於 0。")
        if self.height_px is not None and self.height_px <= 0:
            raise ValueError("height_px 必須大於 0。")

    @property
    def rights_confirmed(self) -> bool:
        return bool(self.rights.strip())

    @property
    def pixel_area(self) -> int:
        return int(self.width_px or 0) * int(self.height_px or 0)

    @property
    def normalized_identity(self) -> tuple[str, ...]:
        isbn = re.sub(r"[^0-9Xx]", "", self.isbn)
        if isbn:
            return ("isbn", isbn.casefold())
        parsed = urlsplit(self.image_url)
        return (
            "metadata-url",
            _normalize(self.title),
            _normalize(self.author),
            parsed.netloc.casefold(),
            parsed.path,
        )

    def with_classification(self, value: CandidateClassification) -> "SearchCandidate":
        return replace(
            self,
            proposed_category=value.category,
            classification_confidence=value.confidence,
            classification_reasons=value.reasons,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "candidate_id": self.candidate_id,
            "query_kind": self.query_kind.value,
            "proposed_category": self.proposed_category.value,
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "isbns": list(self.isbns),
            "preview_url": self.preview_url,
            "image_url": self.image_url,
            "source_page": self.source_page,
            "language": self.language,
            "publisher": self.publisher,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "media_type": self.media_type,
            "rights": self.rights,
            "rights_confirmed": self.rights_confirmed,
            "classification_confidence": self.classification_confidence,
            "classification_reasons": list(self.classification_reasons),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "SearchCandidate":
        return cls(
            provider=str(raw.get("provider", "")),
            candidate_id=str(raw.get("candidate_id", "")),
            query_kind=SearchKind(str(raw.get("query_kind", SearchKind.FRONT.value))),
            proposed_category=CandidateCategory(
                str(raw.get("proposed_category", CandidateCategory.UNKNOWN.value))
            ),
            title=str(raw.get("title", "")),
            author=str(raw.get("author", "")),
            isbn=str(raw.get("isbn", "")),
            isbns=tuple(str(item) for item in raw.get("isbns", []) if str(item).strip()),
            preview_url=str(raw.get("preview_url", "")),
            image_url=str(raw.get("image_url", "")),
            source_page=str(raw.get("source_page", "")),
            language=str(raw.get("language", "")),
            publisher=str(raw.get("publisher", "")),
            width_px=_optional_int(raw.get("width_px")),
            height_px=_optional_int(raw.get("height_px")),
            media_type=str(raw.get("media_type", "")),
            rights=str(raw.get("rights", "")),
            classification_confidence=float(raw.get("classification_confidence", 0.0) or 0.0),
            classification_reasons=tuple(
                str(item) for item in raw.get("classification_reasons", [])
            ),
        )


@dataclass(frozen=True)
class SearchResponse:
    candidates: tuple[SearchCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    resolved_aliases: tuple[ResolvedAlias, ...] = ()
    pending_aliases: tuple[ResolvedAlias, ...] = ()
    resolved_isbns: tuple[str, ...] = ()
    query_items: tuple[QueryItem, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "candidates": [item.to_dict() for item in self.candidates],
            "warnings": list(self.warnings),
            "resolved_aliases": [
                {
                    "value": item.value,
                    "language": item.language,
                    "source": item.source,
                    "confidence": item.confidence,
                    "reasons": list(item.reasons),
                }
                for item in self.resolved_aliases
            ],
            "pending_aliases": [
                {
                    "value": item.value,
                    "language": item.language,
                    "source": item.source,
                    "confidence": item.confidence,
                    "reasons": list(item.reasons),
                }
                for item in self.pending_aliases
            ],
            "resolved_isbns": list(self.resolved_isbns),
            "query_items": [
                {
                    "kind": item.kind,
                    "value": item.value,
                    "author": item.author,
                    "language": item.language,
                    "confidence": item.confidence,
                    "source": item.source,
                    "reason": item.reason,
                }
                for item in self.query_items
            ],
        }


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
