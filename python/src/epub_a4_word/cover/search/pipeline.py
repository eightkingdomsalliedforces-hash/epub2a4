from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .aggregate import merge_candidates
from .alias_cache import AliasCache
from .google_books import GoogleBooksProvider
from .gutendex import GutendexProvider
from .models import (
    BookIdentity,
    CoverSearchRequest,
    QueryItem,
    ResolvedAlias,
    SearchCandidate,
    alias_key,
    SearchKind,
    SearchResponse,
)
from .open_library import OpenLibraryProvider
from .query_plan import build_query_plan, normalize_book_identity, normalize_isbn
from .wikidata import WikidataAliasResolver


@dataclass(frozen=True)
class ProviderSelection:
    google_books: bool = True
    open_library: bool = True
    gutendex: bool = True

    @property
    def any_enabled(self) -> bool:
        return self.google_books or self.open_library or self.gutendex


_PROVIDER_LABELS = {
    "google_books": "Google Books",
    "open_library": "Open Library",
    "gutendex": "Project Gutenberg",
}


class BookCoverSearchPipeline:
    def __init__(
        self,
        http,
        *,
        alias_cache: AliasCache | None = None,
        alias_resolver=None,
        google_provider_factory: Callable[[str], object] | None = None,
        open_library_provider=None,
        gutendex_provider=None,
    ) -> None:
        self.http = http
        self.alias_cache = alias_cache or AliasCache(
            Path.home() / ".epub2a4" / "cover-aliases.json"
        )
        self.alias_resolver = alias_resolver or WikidataAliasResolver(http)
        self.google_provider_factory = google_provider_factory or (
            lambda api_key: GoogleBooksProvider(http, api_key=api_key)
        )
        self.open_library_provider = open_library_provider or OpenLibraryProvider(http)
        self.gutendex_provider = gutendex_provider or GutendexProvider(http)

    def search(
        self,
        metadata: Mapping[str, object],
        *,
        selection: ProviderSelection,
        google_api_key: str = "",
        manual_alias: str = "",
        accepted_aliases: tuple[ResolvedAlias, ...] = (),
        ignored_alias_keys: frozenset[str] = frozenset(),
    ) -> SearchResponse:
        if not selection.any_enabled:
            raise ValueError("至少啟用一個封面搜尋來源。")
        identity = normalize_book_identity(
            title=str(metadata.get("title", "")),
            author=str(metadata.get("author", "")),
            isbn=str(metadata.get("isbn", "")),
            language=str(metadata.get("language", "") or "zh-TW"),
        )
        cached_aliases = self.alias_cache.load(identity)
        resolution = self.alias_resolver.resolve(identity)
        aliases: list[ResolvedAlias] = [*cached_aliases, *resolution.aliases]
        accepted_by_key = {alias_key(alias): alias for alias in accepted_aliases}
        ignored = {str(key).casefold().strip() for key in ignored_alias_keys}
        resolved_isbns: list[str] = list(resolution.isbns)
        warnings: list[str] = list(resolution.warnings)
        candidates: list[SearchCandidate] = []
        executed: dict[str, set[tuple[str, str, str]]] = {
            "google_books": set(),
            "open_library": set(),
            "gutendex": set(),
        }

        google_provider = None
        if selection.google_books:
            if google_api_key.strip():
                google_provider = self.google_provider_factory(google_api_key.strip())
            else:
                warnings.append("Google Books：未設定 API Key，已略過。")

        initial_plan = build_query_plan(
            identity,
            manual_alias=manual_alias,
            aliases=aliases,
            isbns=resolved_isbns,
            accepted_aliases=tuple(accepted_by_key.values()),
        )
        if google_provider is not None:
            google_results = self._run_provider(
                "google_books",
                google_provider,
                initial_plan.items,
                identity,
                executed["google_books"],
                warnings,
            )
            candidates.extend(google_results)
            bridge_aliases, bridge_isbns = self._google_bridge(identity, google_results)
            aliases.extend(bridge_aliases)
            resolved_isbns.extend(bridge_isbns)

        final_plan = build_query_plan(
            identity,
            manual_alias=manual_alias,
            aliases=aliases,
            isbns=resolved_isbns,
            accepted_aliases=tuple(accepted_by_key.values()),
        )
        if google_provider is not None:
            candidates.extend(
                self._run_provider(
                    "google_books",
                    google_provider,
                    final_plan.items,
                    identity,
                    executed["google_books"],
                    warnings,
                )
            )
        if selection.open_library:
            candidates.extend(
                self._run_provider(
                    "open_library",
                    self.open_library_provider,
                    final_plan.items,
                    identity,
                    executed["open_library"],
                    warnings,
                )
            )
        if selection.gutendex:
            title_items = tuple(item for item in final_plan.items if item.kind == "title")
            candidates.extend(
                self._run_provider(
                    "gutendex",
                    self.gutendex_provider,
                    title_items,
                    identity,
                    executed["gutendex"],
                    warnings,
                )
            )

        base_request = CoverSearchRequest(
            kind=SearchKind.FRONT,
            isbn=identity.isbn,
            title=identity.original_title,
            author=identity.author,
            locale=identity.language or "zh-TW",
            max_results=20,
        )
        unique_aliases = self._dedupe_aliases(aliases)
        pending_aliases = tuple(
            alias
            for alias in unique_aliases
            if alias.confidence.casefold() == "medium"
            and alias_key(alias) not in ignored
            and alias_key(alias) not in accepted_by_key
        )
        unique_isbns = tuple(
            dict.fromkeys(
                valid
                for value in resolved_isbns
                if (valid := normalize_isbn(value))
            )
        )
        return SearchResponse(
            candidates=merge_candidates(candidates, base_request),
            warnings=tuple(dict.fromkeys(warnings)),
            resolved_aliases=unique_aliases,
            pending_aliases=pending_aliases,
            resolved_isbns=unique_isbns,
            query_items=final_plan.items,
        )

    def remember_alias(
        self,
        metadata: Mapping[str, object],
        alias: ResolvedAlias,
        *,
        isbn: str = "",
    ) -> None:
        identity = normalize_book_identity(
            title=str(metadata.get("title", "")),
            author=str(metadata.get("author", "")),
            isbn=str(metadata.get("isbn", "")),
            language=str(metadata.get("language", "") or "zh-TW"),
        )
        self.alias_cache.remember(identity, alias, isbn=isbn)

    def clear_alias_cache(self) -> None:
        self.alias_cache.clear()

    @staticmethod
    def _request(item: QueryItem, identity: BookIdentity) -> CoverSearchRequest:
        return CoverSearchRequest(
            kind=SearchKind.FRONT,
            query=item.value,
            isbn=item.value if item.kind == "isbn" else "",
            title=item.value if item.kind == "title" else "",
            author=item.author,
            locale=item.language or identity.language or "zh-TW",
            max_results=20,
        )

    @staticmethod
    def _request_key(item: QueryItem) -> tuple[str, str, str]:
        value = item.value.casefold().strip()
        return (item.kind, value, item.author.casefold().strip())

    def _run_provider(
        self,
        provider_name: str,
        provider,
        items: tuple[QueryItem, ...],
        identity: BookIdentity,
        executed: set[tuple[str, str, str]],
        warnings: list[str],
    ) -> list[SearchCandidate]:
        found: list[SearchCandidate] = []
        label = _PROVIDER_LABELS[provider_name]
        for item in items:
            key = self._request_key(item)
            if key in executed:
                continue
            executed.add(key)
            try:
                response = provider.search(self._request(item, identity))
            except Exception as exc:
                warnings.append(f"{label}：{exc}")
                continue
            found.extend(response.candidates)
            warnings.extend(
                warning if warning.startswith(f"{label}：") else f"{label}：{warning}"
                for warning in response.warnings
            )
        return found

    @staticmethod
    def _google_bridge(
        identity: BookIdentity,
        candidates: list[SearchCandidate],
    ) -> tuple[tuple[ResolvedAlias, ...], tuple[str, ...]]:
        aliases: list[ResolvedAlias] = []
        isbns: list[str] = []
        identity_author = identity.normalized_author.casefold().strip()
        for candidate in candidates:
            candidate_isbn = normalize_isbn(candidate.isbn)
            if candidate_isbn:
                isbns.append(candidate_isbn)
            title = candidate.title.strip()
            if not title:
                continue
            author = " ".join(candidate.author.casefold().split())
            confidence = "high" if not identity_author or author == identity_author else "medium"
            aliases.append(
                ResolvedAlias(
                    value=title,
                    language=candidate.language or None,
                    source="google_books",
                    confidence=confidence,
                    reasons=(
                        "Google Books ISBN" if candidate_isbn else "Google Books 書目結果",
                    ),
                )
            )
        return BookCoverSearchPipeline._dedupe_aliases(aliases), tuple(dict.fromkeys(isbns))

    @staticmethod
    def _dedupe_aliases(aliases) -> tuple[ResolvedAlias, ...]:
        unique: dict[tuple[str, str], ResolvedAlias] = {}
        for alias in aliases:
            key = (alias.value.casefold().strip(), (alias.language or "").casefold())
            if not key[0]:
                continue
            current = unique.get(key)
            if current is None or (current.confidence != "high" and alias.confidence == "high"):
                unique[key] = alias
        return tuple(unique.values())
