from __future__ import annotations

from epub_a4_word.cover.search.aggregate import build_general_requests
from epub_a4_word.cover.search.classifier import classify_candidate
from epub_a4_word.cover.search.errors import SearchTransportError
from epub_a4_word.cover.search.models import (
    CandidateCategory,
    CoverSearchRequest,
    ProviderCredential,
    SearchCandidate,
    SearchKind,
)


def _candidate(kind: SearchKind, *, width: int = 1000, height: int = 1500) -> SearchCandidate:
    return SearchCandidate(
        provider="google_custom",
        candidate_id=kind.value,
        query_kind=kind,
        proposed_category=CandidateCategory(kind.value),
        title=f"Example {kind.value}",
        author="",
        isbn="9780000000001",
        preview_url="https://example.test/preview.jpg",
        image_url=f"https://example.test/{kind.value}.jpg",
        source_page="https://example.test/book",
        width_px=width,
        height_px=height,
        media_type="image/jpeg",
    )


def test_general_search_builds_five_existing_image_queries_and_classifies_parts():
    requests = build_general_requests(
        title="範例書",
        author="作者",
        isbn="9780000000001",
        locale="zh-TW",
    )
    assert tuple(request.kind for request in requests) == tuple(SearchKind)
    assert all("範例書" in request.query for request in requests)

    spine = classify_candidate(_candidate(SearchKind.SPINE, width=100, height=1000))
    spread = classify_candidate(_candidate(SearchKind.FULL_SPREAD, width=1800, height=1000))
    assert spine.category is CandidateCategory.SPINE
    assert spread.category is CandidateCategory.FULL_SPREAD


def test_credentials_are_not_part_of_requests_candidates_or_safe_errors():
    credential = ProviderCredential("VERY_SECRET_API_KEY", "VERY_SECRET_ENGINE")
    request = CoverSearchRequest(kind=SearchKind.FRONT, title="範例書")
    candidate = _candidate(SearchKind.FRONT)
    serialized = repr((request.to_dict(), candidate.to_dict()))
    assert credential.api_key not in serialized
    assert credential.search_engine_id not in serialized

    error = SearchTransportError(
        "request failed",
        url="https://example.test/search?key=VERY_SECRET_API_KEY",
        params={
            "key": credential.api_key,
            "cx": credential.search_engine_id,
            "q": "範例書",
        },
    )
    assert credential.api_key not in repr(error)
    assert credential.search_engine_id not in repr(error)
