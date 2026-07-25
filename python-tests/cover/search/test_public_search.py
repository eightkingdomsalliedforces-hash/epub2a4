from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from epub_a4_word.cover.search.aggregate import PublicBookSearch
from epub_a4_word.cover.search.google_books import GoogleBooksProvider
from epub_a4_word.cover.search.models import (
    CandidateCategory,
    CoverSearchRequest,
    SearchKind,
)
from epub_a4_word.cover.search.open_library import OpenLibraryProvider


_FIXTURES = Path(__file__).parents[2] / "fixtures" / "search"


class FixtureHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(
        self,
        url: str,
        params: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        del headers
        self.calls.append((url, dict(params)))
        host = urlsplit(url).hostname
        if host == "www.googleapis.com":
            filename = "google-books-isbn.json"
        elif host == "openlibrary.org":
            filename = "open-library-title.json"
        else:
            raise AssertionError(f"unexpected endpoint: {url}")
        return json.loads((_FIXTURES / filename).read_text(encoding="utf-8"))


def test_public_search_merges_deduplicates_and_ranks_exact_isbn() -> None:
    client = FixtureHttpClient()
    public_search = PublicBookSearch(
        GoogleBooksProvider(client),
        OpenLibraryProvider(client),
    )

    response = public_search.search(
        CoverSearchRequest(
            kind=SearchKind.FRONT,
            isbn="978-0-000000-00-1",
            title="範例書",
            author="作者",
        )
    )

    assert response.candidates
    assert response.candidates[0].isbn == "9780000000001"
    assert response.candidates[0].provider == "google_books"
    assert response.candidates[0].image_url.startswith("https://")
    assert len({candidate.normalized_identity for candidate in response.candidates}) == len(
        response.candidates
    )
    assert all(
        candidate.proposed_category is CandidateCategory.FRONT
        for candidate in response.candidates
    )
    assert response.query_count == 2

    google_call = next(call for call in client.calls if "googleapis" in call[0])
    open_library_call = next(call for call in client.calls if "openlibrary" in call[0])
    assert google_call[1]["q"] == "isbn:9780000000001"
    assert open_library_call[1]["isbn"] == "9780000000001"
    assert "cover_i" in str(open_library_call[1]["fields"])


def test_public_search_falls_back_to_title_and_author_queries() -> None:
    client = FixtureHttpClient()
    public_search = PublicBookSearch(
        GoogleBooksProvider(client),
        OpenLibraryProvider(client),
    )

    public_search.search(
        CoverSearchRequest(
            kind=SearchKind.FRONT,
            title="範例書",
            author="作者",
        )
    )

    google_call = next(call for call in client.calls if "googleapis" in call[0])
    open_library_call = next(call for call in client.calls if "openlibrary" in call[0])
    assert google_call[1]["q"] == "intitle:範例書 inauthor:作者"
    assert open_library_call[1]["title"] == "範例書"
    assert open_library_call[1]["author"] == "作者"
