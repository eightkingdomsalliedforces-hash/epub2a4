from __future__ import annotations

import re
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from .errors import SearchResponseError
from .models import (
    CandidateCategory,
    CoverSearchRequest,
    SearchCandidate,
    SearchResponse,
)

_GOOGLE_BOOKS_ENDPOINT = "https://www.googleapis.com/books/v1/volumes"
_IMAGE_PREFERENCE = (
    "extraLarge",
    "large",
    "medium",
    "small",
    "thumbnail",
    "smallThumbnail",
)


class JsonClient(Protocol):
    def get_json(
        self,
        url: str,
        params: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]: ...


def _normalize_isbn(value: object) -> str:
    return re.sub(r"[^0-9xX]", "", str(value or "")).upper()


def _https_google_url(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme == "http" and (
        host == "books.google.com" or host.endswith(".google.com")
    ):
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    if parsed.scheme == "https":
        return text
    return ""


def _first_text(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def _select_isbn(volume: dict[str, object], requested_isbn: str) -> str:
    identifiers = volume.get("industryIdentifiers")
    normalized: list[tuple[str, str]] = []
    if isinstance(identifiers, list):
        for item in identifiers:
            if not isinstance(item, dict):
                continue
            identifier = _normalize_isbn(item.get("identifier"))
            if identifier:
                normalized.append((str(item.get("type", "")), identifier))
    if requested_isbn:
        for _kind, identifier in normalized:
            if identifier == requested_isbn:
                return identifier
    for preferred_type in ("ISBN_13", "ISBN_10"):
        for kind, identifier in normalized:
            if kind == preferred_type:
                return identifier
    return normalized[0][1] if normalized else ""


def _image_links(volume: dict[str, object]) -> tuple[str, str]:
    links = volume.get("imageLinks")
    if not isinstance(links, dict):
        return "", ""
    selected = ""
    for key in _IMAGE_PREFERENCE:
        selected = _https_google_url(links.get(key))
        if selected:
            break
    preview = _https_google_url(links.get("thumbnail")) or selected
    return selected, preview


class GoogleBooksProvider:
    provider_name = "google_books"

    def __init__(self, client: JsonClient) -> None:
        self._client = client

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        requested_isbn = _normalize_isbn(request.isbn)
        if requested_isbn:
            query = f"isbn:{requested_isbn}"
        else:
            parts: list[str] = []
            if request.title.strip():
                parts.append(f"intitle:{request.title.strip()}")
            if request.author.strip():
                parts.append(f"inauthor:{request.author.strip()}")
            if not parts and request.query.strip():
                parts.append(request.query.strip())
            query = " ".join(parts)

        payload = self._client.get_json(
            _GOOGLE_BOOKS_ENDPOINT,
            {
                "q": query,
                "maxResults": request.max_results,
                "printType": "books",
                "langRestrict": request.locale.split("-", 1)[0],
            },
        )
        items = payload.get("items", [])
        if items is None:
            items = []
        if not isinstance(items, list):
            raise SearchResponseError("Google Books 回應的 items 格式無效。")

        candidates: list[SearchCandidate] = []
        warnings: list[str] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                warnings.append(f"Google Books 第 {index + 1} 筆結果格式無效，已略過。")
                continue
            volume = item.get("volumeInfo")
            if not isinstance(volume, dict):
                continue
            image_url, preview_url = _image_links(volume)
            if not image_url:
                continue
            candidate_id = str(item.get("id", "")).strip()
            if not candidate_id:
                continue
            source_page = _https_google_url(
                volume.get("infoLink") or volume.get("canonicalVolumeLink")
            )
            if not source_page:
                source_page = f"https://books.google.com/books?id={candidate_id}"
            title = str(volume.get("title", "")).strip()
            author = _first_text(volume.get("authors"))
            isbn = _select_isbn(volume, requested_isbn)
            candidates.append(
                SearchCandidate(
                    provider=self.provider_name,
                    candidate_id=candidate_id,
                    query_kind=request.kind,
                    proposed_category=CandidateCategory.FRONT,
                    title=title,
                    author=author,
                    isbn=isbn,
                    preview_url=preview_url,
                    image_url=image_url,
                    source_page=source_page,
                    media_type="image/jpeg",
                )
            )

        return SearchResponse(
            candidates=tuple(candidates[: request.max_results]),
            warnings=tuple(warnings),
            query_count=1,
        )
