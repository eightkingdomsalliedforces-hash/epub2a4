from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from .errors import CoverSearchError
from .models import CoverSearchRequest, SearchCandidate, SearchResponse

_PROVIDER_ORDER = {
    "google_books": 0,
    "open_library": 1,
}


class SearchProvider(Protocol):
    def search(self, request: CoverSearchRequest) -> SearchResponse: ...


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(normalized.split())


def _normalize_isbn(value: str) -> str:
    return re.sub(r"[^0-9xX]", "", value).upper()


def _pixel_area(candidate: SearchCandidate) -> int:
    if candidate.width_px is None or candidate.height_px is None:
        return 0
    return candidate.width_px * candidate.height_px


def _rank_key(
    candidate: SearchCandidate,
    request: CoverSearchRequest,
) -> tuple[object, ...]:
    requested_isbn = _normalize_isbn(request.isbn)
    candidate_isbn = _normalize_isbn(candidate.isbn)
    requested_title = _normalize_text(request.title)
    requested_author = _normalize_text(request.author)
    candidate_title = _normalize_text(candidate.title)
    candidate_author = _normalize_text(candidate.author)

    exact_isbn = bool(requested_isbn and candidate_isbn == requested_isbn)
    exact_title = bool(requested_title and candidate_title == requested_title)
    exact_author = bool(requested_author and candidate_author == requested_author)
    exact_title_author = exact_title and (
        exact_author if requested_author else not candidate_author
    )
    return (
        0 if exact_isbn else 1,
        0 if exact_title_author else 1,
        0 if exact_title else 1,
        -_pixel_area(candidate),
        _PROVIDER_ORDER.get(candidate.provider, 99),
        candidate.candidate_id,
    )


class PublicBookSearch:
    def __init__(
        self,
        google_books: SearchProvider,
        open_library: SearchProvider,
    ) -> None:
        self._providers = (google_books, open_library)

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        candidates: list[SearchCandidate] = []
        warnings: list[str] = []
        query_count = 0

        for provider in self._providers:
            try:
                response = provider.search(request)
            except CoverSearchError as exc:
                warnings.append(str(exc))
                query_count += 1
                continue
            candidates.extend(response.candidates)
            warnings.extend(response.warnings)
            query_count += response.query_count

        ranked = sorted(candidates, key=lambda candidate: _rank_key(candidate, request))
        deduplicated: list[SearchCandidate] = []
        seen: set[str] = set()
        for candidate in ranked:
            identity = candidate.normalized_identity
            if identity in seen:
                continue
            seen.add(identity)
            deduplicated.append(candidate)
            if len(deduplicated) >= request.max_results:
                break

        return SearchResponse(
            candidates=tuple(deduplicated),
            warnings=tuple(dict.fromkeys(warnings)),
            query_count=query_count,
        )
