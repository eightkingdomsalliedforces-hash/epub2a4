from __future__ import annotations

from collections.abc import Iterable
import re

from .classifier import classify_candidate
from .models import (
    CandidateCategory,
    CoverSearchRequest,
    ProviderCredential,
    SearchCandidate,
    SearchKind,
    SearchResponse,
)

PROVIDER_ORDER = {
    "google_books": 0,
    "open_library": 1,
    "gutendex": 2,
    "google_custom": 3,
}
QUERY_TERMS = {
    SearchKind.FRONT: ("封面", "front cover"),
    SearchKind.BACK: ("背面 封底", "back cover"),
    SearchKind.SPINE: ("書脊", "book spine"),
    SearchKind.FULL_SPREAD: ("完整書衣 展開圖", "full dust jacket wraparound cover"),
    SearchKind.REFERENCE_PHOTO: ("實拍 多角度", "book photos alternate angles"),
}


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _rank(candidate: SearchCandidate, request: CoverSearchRequest) -> tuple[object, ...]:
    requested_isbn = re.sub(r"[^0-9Xx]", "", request.isbn)
    candidate_isbn = re.sub(r"[^0-9Xx]", "", candidate.isbn)
    exact_isbn = bool(requested_isbn and candidate_isbn.casefold() == requested_isbn.casefold())
    exact_title = bool(request.title and _normalize(candidate.title) == _normalize(request.title))
    exact_author = bool(request.author and _normalize(candidate.author) == _normalize(request.author))
    return (
        0 if exact_isbn else 1,
        0 if exact_title and exact_author else 1,
        0 if exact_title else 1,
        -candidate.pixel_area,
        PROVIDER_ORDER.get(candidate.provider, 99),
        candidate.candidate_id,
    )


def merge_candidates(
    candidates: Iterable[SearchCandidate],
    request: CoverSearchRequest,
) -> tuple[SearchCandidate, ...]:
    unique: dict[tuple[str, ...], SearchCandidate] = {}
    for candidate in candidates:
        current = unique.get(candidate.normalized_identity)
        if current is None or _rank(candidate, request) < _rank(current, request):
            unique[candidate.normalized_identity] = candidate
    return tuple(sorted(unique.values(), key=lambda item: _rank(item, request)))


class PublicBookSearch:
    def __init__(self, providers: Iterable[object]) -> None:
        self.providers = tuple(providers)

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        request = CoverSearchRequest(
            kind=SearchKind.FRONT,
            query=request.query,
            isbn=request.isbn,
            title=request.title,
            author=request.author,
            locale=request.locale,
            max_results=request.max_results,
            safe_search=request.safe_search,
        )
        found: list[SearchCandidate] = []
        warnings: list[str] = []
        for provider in self.providers:
            try:
                response = provider.search(request)
            except Exception as exc:
                warnings.append(str(exc))
                continue
            found.extend(response.candidates)
            warnings.extend(response.warnings)
        classified = [
            item.with_classification(classify_candidate(item, SearchKind.FRONT)) for item in found
        ]
        return SearchResponse(merge_candidates(classified, request), tuple(dict.fromkeys(warnings)))


def build_general_requests(
    *,
    title: str,
    author: str = "",
    isbn: str = "",
    locale: str = "zh-TW",
    max_results: int = 10,
) -> tuple[CoverSearchRequest, ...]:
    identity_parts = [f'"{title.strip()}"' if title.strip() else ""]
    if author.strip():
        identity_parts.append(f'"{author.strip()}"')
    if isbn.strip():
        identity_parts.append(isbn.strip())
    base = " ".join(part for part in identity_parts if part)
    requests = []
    for kind, terms in QUERY_TERMS.items():
        query = " ".join((base, *terms)).strip()
        requests.append(
            CoverSearchRequest(
                kind=kind,
                query=query,
                isbn=isbn,
                title=title,
                author=author,
                locale=locale,
                max_results=min(max_results, 10),
            )
        )
    return tuple(requests)


class GeneralCoverSearch:
    def __init__(self, provider) -> None:
        self.provider = provider

    def search_all(
        self,
        *,
        title: str,
        author: str = "",
        isbn: str = "",
        locale: str = "zh-TW",
        credential: ProviderCredential,
        max_results: int = 10,
    ) -> SearchResponse:
        candidates: list[SearchCandidate] = []
        warnings: list[str] = []
        for request in build_general_requests(
            title=title,
            author=author,
            isbn=isbn,
            locale=locale,
            max_results=max_results,
        ):
            try:
                response = self.provider.search(request, credential)
            except Exception as exc:
                warnings.append(f"{request.kind.value}: {exc}")
                continue
            candidates.extend(response.candidates)
            warnings.extend(response.warnings)
        # General image results from different query kinds are intentionally not
        # deduplicated solely by title because one source page may contain several parts.
        unique: dict[tuple[str, str], SearchCandidate] = {}
        for item in candidates:
            key = (item.query_kind.value, item.image_url)
            unique.setdefault(key, item)
        ordered = tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    list(SearchKind).index(item.query_kind),
                    -item.classification_confidence,
                    -item.pixel_area,
                    item.candidate_id,
                ),
            )
        )
        return SearchResponse(ordered, tuple(dict.fromkeys(warnings)))
