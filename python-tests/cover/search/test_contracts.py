from pathlib import Path

import pytest

from epub_a4_word.cover.search.errors import SearchTransportError
from epub_a4_word.cover.search.http import JsonHttpClient
from epub_a4_word.cover.search.models import (
    CandidateCategory,
    CoverSearchRequest,
    SearchCandidate,
    SearchKind,
)


def test_request_and_candidate_contracts_reject_unsafe_values() -> None:
    request = CoverSearchRequest(
        kind=SearchKind.FRONT,
        title="範例書",
        author="作者",
        locale="zh-TW",
        max_results=20,
    )
    candidate = SearchCandidate(
        provider="google_books",
        candidate_id="volume-1",
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title="範例書",
        author="作者",
        isbn="9780000000001",
        preview_url="https://example.test/preview.jpg",
        image_url="https://example.test/original.jpg",
        source_page="https://example.test/book/1",
        width_px=1200,
        height_px=1800,
        media_type="image/jpeg",
        rights="",
    )

    assert request.max_results == 20
    assert candidate.rights_confirmed is False

    client = JsonHttpClient()
    with pytest.raises(SearchTransportError, match="HTTPS"):
        client.get_json("http://example.test/data", {})

    with pytest.raises(ValueError, match="HTTPS"):
        SearchCandidate(
            provider="unsafe",
            candidate_id="candidate-1",
            query_kind=SearchKind.FRONT,
            proposed_category=CandidateCategory.FRONT,
            title="Unsafe",
            author="",
            isbn="",
            preview_url="",
            image_url="http://example.test/image.jpg",
            source_page="",
        )


@pytest.mark.parametrize("max_results", [0, 41])
def test_request_rejects_result_limits_outside_contract(max_results: int) -> None:
    with pytest.raises(ValueError, match="max_results"):
        CoverSearchRequest(
            kind=SearchKind.FRONT,
            title="範例書",
            max_results=max_results,
        )


def test_request_requires_query_isbn_or_title() -> None:
    with pytest.raises(ValueError, match="搜尋"):
        CoverSearchRequest(kind=SearchKind.FRONT, author="只有作者")


def test_stream_download_rejects_non_https_before_creating_file(tmp_path: Path) -> None:
    destination = tmp_path / "candidate.bin"
    client = JsonHttpClient()

    with pytest.raises(SearchTransportError, match="HTTPS"):
        client.stream_download("http://example.test/image.jpg", destination, 1024)

    assert not destination.exists()
