from __future__ import annotations

import json
from pathlib import Path

import pytest

from epub_a4_word.cover.search.alias_cache import AliasCache
from epub_a4_word.cover.search.models import (
    CandidateCategory,
    ResolvedAlias,
    SearchCandidate,
    SearchKind,
    SearchResponse,
)
from epub_a4_word.cover.search.pipeline import (
    BookCoverSearchPipeline,
    ProviderSelection,
)
from epub_a4_word.cover.search.query_plan import normalize_book_identity
from epub_a4_word.cover.search.wikidata import AliasResolution


def _candidate(provider: str, candidate_id: str, *, title="Book", isbn=""):
    return SearchCandidate(
        provider=provider,
        candidate_id=candidate_id,
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title=title,
        author="Author",
        isbn=isbn,
        preview_url=f"https://example.test/{candidate_id}-preview.jpg",
        image_url=f"https://example.test/{candidate_id}.jpg",
        source_page=f"https://example.test/{candidate_id}",
        media_type="image/jpeg",
    )


class FakeProvider:
    def __init__(self, name: str, callback=None, error: Exception | None = None) -> None:
        self.name = name
        self.callback = callback or (lambda request: SearchResponse())
        self.error = error
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.callback(request)


class FakeGoogleFactory:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider
        self.keys: list[str] = []

    def __call__(self, api_key: str):
        self.keys.append(api_key)
        return self.provider


class FakeResolver:
    def __init__(self, resolution: AliasResolution | None = None) -> None:
        self.resolution = resolution or AliasResolution((), ())
        self.identities = []

    def resolve(self, identity):
        self.identities.append(identity)
        return self.resolution


def _pipeline(
    tmp_path: Path,
    *,
    google=None,
    open_library=None,
    gutendex=None,
    resolver=None,
):
    google_provider = google or FakeProvider("google_books")
    google_factory = FakeGoogleFactory(google_provider)
    pipeline = BookCoverSearchPipeline(
        http=object(),
        alias_cache=AliasCache(tmp_path / "aliases.json"),
        alias_resolver=resolver or FakeResolver(),
        google_provider_factory=google_factory,
        open_library_provider=open_library or FakeProvider("open_library"),
        gutendex_provider=gutendex or FakeProvider("gutendex"),
    )
    return pipeline, google_factory


def test_missing_google_key_skips_only_google_books(tmp_path: Path) -> None:
    open_library = FakeProvider(
        "open_library",
        lambda request: SearchResponse((_candidate("open_library", "ol"),)),
    )
    gutendex = FakeProvider(
        "gutendex",
        lambda request: SearchResponse((_candidate("gutendex", "pg"),)),
    )
    pipeline, google_factory = _pipeline(
        tmp_path, open_library=open_library, gutendex=gutendex
    )

    response = pipeline.search(
        {"title": "Book", "author": "Author", "isbn": "", "language": "en"},
        selection=ProviderSelection(),
    )

    assert google_factory.keys == []
    assert {item.provider for item in response.candidates} == {"open_library", "gutendex"}
    assert "Google Books：未設定 API Key，已略過。" in response.warnings


def test_google_books_and_wikidata_expand_later_open_library_queries(tmp_path: Path) -> None:
    valid_isbn = "9780306406157"

    def google_callback(request):
        if request.title == "中文譯名":
            return SearchResponse(
                (_candidate("google_books", "gb", title="Original Title", isbn=valid_isbn),)
            )
        return SearchResponse()

    google = FakeProvider("google_books", google_callback)
    open_library = FakeProvider(
        "open_library",
        lambda request: SearchResponse(
            (_candidate("open_library", "ol", title=request.title or "ISBN", isbn=request.isbn),)
        ),
    )
    resolver = FakeResolver(
        AliasResolution(
            (
                ResolvedAlias(
                    value="原題",
                    language="ja",
                    source="wikidata",
                    confidence="high",
                    reasons=("書名相符",),
                ),
            ),
            (),
        )
    )
    pipeline, google_factory = _pipeline(
        tmp_path, google=google, open_library=open_library, resolver=resolver
    )

    response = pipeline.search(
        {"title": "中文譯名", "author": "Author", "isbn": "", "language": "zh-TW"},
        selection=ProviderSelection(gutendex=False),
        google_api_key="BOOKS_KEY",
    )

    assert google_factory.keys == ["BOOKS_KEY"]
    assert any(request.isbn == valid_isbn for request in open_library.requests)
    assert any(request.title == "Original Title" for request in open_library.requests)
    assert any(request.title == "原題" for request in open_library.requests)
    assert {item.provider for item in response.candidates} == {"google_books", "open_library"}


def test_manual_alias_is_first_title_query_and_duplicate_queries_run_once(tmp_path: Path) -> None:
    open_library = FakeProvider("open_library")
    resolver = FakeResolver(
        AliasResolution(
            (
                ResolvedAlias(
                    value="ORIGINAL TITLE",
                    language="en",
                    source="wikidata",
                    confidence="high",
                    reasons=(),
                ),
            ),
            (),
        )
    )
    pipeline, _ = _pipeline(tmp_path, open_library=open_library, resolver=resolver)

    pipeline.search(
        {"title": "Translated 01", "author": "Author", "language": "en"},
        selection=ProviderSelection(google_books=False, gutendex=False),
        manual_alias=" original title ",
    )

    title_requests = [request.title for request in open_library.requests if request.title]
    assert title_requests[0] == "original title"
    assert sum(value.casefold() == "original title" for value in title_requests) == 1


def test_provider_failure_preserves_other_results(tmp_path: Path) -> None:
    open_library = FakeProvider("open_library", error=RuntimeError("rate limited"))
    gutendex = FakeProvider(
        "gutendex",
        lambda request: SearchResponse((_candidate("gutendex", "pg"),)),
    )
    pipeline, _ = _pipeline(tmp_path, open_library=open_library, gutendex=gutendex)

    response = pipeline.search(
        {"title": "Book", "author": "Author", "language": "en"},
        selection=ProviderSelection(google_books=False),
    )

    assert [item.provider for item in response.candidates] == ["gutendex"]
    assert "Open Library：rate limited" in response.warnings


def test_all_disabled_provider_selection_is_invalid(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path)

    with pytest.raises(ValueError, match="至少啟用一個"):
        pipeline.search(
            {"title": "Book"},
            selection=ProviderSelection(False, False, False),
        )


def test_alias_cache_reuses_series_alias_but_never_old_volume_isbn(tmp_path: Path) -> None:
    cache_path = tmp_path / "aliases.json"
    cache = AliasCache(cache_path)
    first = normalize_book_identity(title="Series 01", author="Author")
    second = normalize_book_identity(title="Series 02", author="Author")
    alias = ResolvedAlias(
        value="Original Series",
        language="ja",
        source="user",
        confidence="high",
        reasons=("confirmed",),
    )

    cache.remember(first, alias, isbn="9780306406157")
    loaded = cache.load(second)

    assert [item.value for item in loaded] == ["Original Series"]
    raw = json.loads(cache_path.read_text("utf-8"))
    serialized = json.dumps(raw, ensure_ascii=False)
    assert "9780306406157" in serialized
    assert "epub" not in serialized.casefold()
    assert "body" not in serialized.casefold()
    assert all("isbn" not in item.reasons for item in loaded)


def test_ignored_alias_is_not_returned_as_pending(tmp_path: Path) -> None:
    alias = ResolvedAlias(
        value="A Certain Magical Index",
        language="en",
        source="wikidata",
        confidence="medium",
        reasons=("same work",),
    )
    resolver = FakeResolver(AliasResolution((alias,), ()))
    pipeline, _ = _pipeline(tmp_path, resolver=resolver)

    response = pipeline.search(
        {"title": "魔法禁書目錄", "author": "鎌池和馬", "language": "zh-TW"},
        selection=ProviderSelection(
            open_library=True,
            google_books=False,
            gutendex=False,
        ),
        ignored_alias_keys=frozenset(
            {"wikidata|en|a certain magical index"}
        ),
    )

    assert all(
        item.value != "A Certain Magical Index"
        for item in response.pending_aliases
    )


def test_accepted_medium_alias_is_queried_but_remains_resolved_metadata(
    tmp_path: Path,
) -> None:
    alias = ResolvedAlias(
        value="A Certain Magical Index",
        language="en",
        source="wikidata",
        confidence="medium",
        reasons=("same work",),
    )
    resolver = FakeResolver(AliasResolution((alias,), ()))
    open_library = FakeProvider("open_library")
    pipeline, _ = _pipeline(
        tmp_path,
        resolver=resolver,
        open_library=open_library,
    )

    response = pipeline.search(
        {"title": "魔法禁書目錄", "author": "鎌池和馬", "language": "zh-TW"},
        selection=ProviderSelection(
            open_library=True,
            google_books=False,
            gutendex=False,
        ),
        accepted_aliases=(alias,),
    )

    assert any(
        request.title == "A Certain Magical Index"
        for request in open_library.requests
    )
    assert alias in response.resolved_aliases
    assert alias not in response.pending_aliases


def test_alias_cache_promotes_remembered_medium_alias_to_confirmed_high(
    tmp_path: Path,
) -> None:
    cache = AliasCache(tmp_path / "aliases.json")
    identity = normalize_book_identity(title="魔法禁書目錄 01", author="鎌池和馬")
    cache.remember(
        identity,
        ResolvedAlias(
            value="A Certain Magical Index",
            language="en",
            source="wikidata",
            confidence="medium",
            reasons=("user confirmed",),
        ),
    )

    loaded = cache.load(identity)

    assert len(loaded) == 1
    assert loaded[0].value == "A Certain Magical Index"
    assert loaded[0].confidence == "high"
    assert loaded[0].source == "local_cache"
