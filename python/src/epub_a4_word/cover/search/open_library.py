from __future__ import annotations

import re
from typing import Protocol

from .errors import SearchResponseError
from .models import (
    CandidateCategory,
    CoverSearchRequest,
    SearchCandidate,
    SearchResponse,
)

_OPEN_LIBRARY_ENDPOINT = "https://openlibrary.org/search.json"
_OPEN_LIBRARY_FIELDS = "key,title,author_name,isbn,cover_i,edition_key"


class JsonClient(Protocol):
    def get_json(
        self,
        url: str,
        params: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]: ...


def _normalize_isbn(value: object) -> str:
    return re.sub(r"[^0-9xX]", "", str(value or "")).upper()


def _first_text(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def _select_isbn(value: object, requested_isbn: str) -> str:
    raw_values = value if isinstance(value, list) else [value]
    normalized = [_normalize_isbn(item) for item in raw_values]
    normalized = [item for item in normalized if item]
    if requested_isbn in normalized:
        return requested_isbn
    for item in normalized:
        if len(item) == 13:
            return item
    return normalized[0] if normalized else ""


class OpenLibraryProvider:
    provider_name = "open_library"

    def __init__(self, client: JsonClient) -> None:
        self._client = client

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        requested_isbn = _normalize_isbn(request.isbn)
        params: dict[str, object] = {
            "fields": _OPEN_LIBRARY_FIELDS,
            "limit": request.max_results,
        }
        if requested_isbn:
            params["isbn"] = requested_isbn
        else:
            if request.title.strip():
                params["title"] = request.title.strip()
            if request.author.strip():
                params["author"] = request.author.strip()
            if not request.title.strip() and request.query.strip():
                params["q"] = request.query.strip()

        payload = self._client.get_json(_OPEN_LIBRARY_ENDPOINT, params)
        docs = payload.get("docs", [])
        if docs is None:
            docs = []
        if not isinstance(docs, list):
            raise SearchResponseError("Open Library 回應的 docs 格式無效。")

        candidates: list[SearchCandidate] = []
        warnings: list[str] = []
        for index, doc in enumerate(docs):
            if not isinstance(doc, dict):
                warnings.append(f"Open Library 第 {index + 1} 筆結果格式無效，已略過。")
                continue
            cover_id = doc.get("cover_i")
            try:
                cover_number = int(cover_id)
            except (TypeError, ValueError):
                continue
            if cover_number <= 0:
                continue
            edition_key = _first_text(doc.get("edition_key"))
            work_key = str(doc.get("key", "")).strip()
            candidate_id = edition_key or work_key.strip("/").replace("/", "-")
            if not candidate_id:
                continue
            source_page = f"https://openlibrary.org{work_key}" if work_key.startswith("/") else ""
            if not source_page:
                source_page = f"https://openlibrary.org/books/{candidate_id}"
            candidates.append(
                SearchCandidate(
                    provider=self.provider_name,
                    candidate_id=candidate_id,
                    query_kind=request.kind,
                    proposed_category=CandidateCategory.FRONT,
                    title=str(doc.get("title", "")).strip(),
                    author=_first_text(doc.get("author_name")),
                    isbn=_select_isbn(doc.get("isbn"), requested_isbn),
                    preview_url=f"https://covers.openlibrary.org/b/id/{cover_number}-M.jpg",
                    image_url=f"https://covers.openlibrary.org/b/id/{cover_number}-L.jpg",
                    source_page=source_page,
                    media_type="image/jpeg",
                )
            )

        return SearchResponse(
            candidates=tuple(candidates[: request.max_results]),
            warnings=tuple(warnings),
            query_count=1,
        )
