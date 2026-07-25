from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import unicodedata
from urllib.parse import urlsplit


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


def _require_https(value: str, field_name: str) -> None:
    if value and urlsplit(value).scheme.lower() != "https":
        raise ValueError(f"{field_name} 必須使用 HTTPS。")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(normalized.split())


def _normalize_isbn(value: str) -> str:
    return re.sub(r"[^0-9xX]", "", value).upper()


@dataclass(frozen=True)
class CoverSearchRequest:
    kind: SearchKind
    query: str = ""
    isbn: str = ""
    title: str = ""
    author: str = ""
    locale: str = "zh-TW"
    max_results: int = 20
    safe_search: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.max_results <= 40:
            raise ValueError("max_results 必須介於 1 與 40。")
        if not any(value.strip() for value in (self.query, self.isbn, self.title)):
            raise ValueError("搜尋至少需要關鍵字、ISBN 或書名。")
        if not self.locale.strip():
            raise ValueError("locale 不可為空。")

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
    search_engine_id: str

    @property
    def complete(self) -> bool:
        return bool(self.api_key.strip() and self.search_engine_id.strip())


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
    width_px: int | None = None
    height_px: int | None = None
    media_type: str = ""
    rights: str = ""
    classification_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider 不可為空。")
        if not self.candidate_id.strip():
            raise ValueError("candidate_id 不可為空。")
        for field_name, value in (
            ("preview_url", self.preview_url),
            ("image_url", self.image_url),
            ("source_page", self.source_page),
        ):
            _require_https(value, field_name)
        if not self.image_url:
            raise ValueError("image_url 不可為空。")
        if self.width_px is not None and self.width_px <= 0:
            raise ValueError("width_px 必須大於 0。")
        if self.height_px is not None and self.height_px <= 0:
            raise ValueError("height_px 必須大於 0。")
        if not 0.0 <= self.classification_confidence <= 1.0:
            raise ValueError("classification_confidence 必須介於 0 與 1。")

    @property
    def rights_confirmed(self) -> bool:
        return bool(self.rights.strip())

    @property
    def normalized_identity(self) -> str:
        isbn = _normalize_isbn(self.isbn)
        if isbn:
            return f"isbn:{isbn}"
        parsed = urlsplit(self.image_url)
        return "|".join(
            (
                _normalize_text(self.title),
                _normalize_text(self.author),
                parsed.hostname.casefold() if parsed.hostname else "",
                parsed.path.casefold(),
            )
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
            "preview_url": self.preview_url,
            "image_url": self.image_url,
            "source_page": self.source_page,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "media_type": self.media_type,
            "rights": self.rights,
            "rights_confirmed": self.rights_confirmed,
            "classification_confidence": self.classification_confidence,
        }


@dataclass(frozen=True)
class CandidateClassification:
    category: CandidateCategory
    confidence: float
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence 必須介於 0 與 1。")

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class SearchResponse:
    candidates: tuple[SearchCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    query_count: int = 1

    def __post_init__(self) -> None:
        if self.query_count < 0:
            raise ValueError("query_count 不可小於 0。")

    def to_dict(self) -> dict[str, object]:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
            "query_count": self.query_count,
        }
