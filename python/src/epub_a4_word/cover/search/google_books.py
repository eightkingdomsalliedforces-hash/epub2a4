from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .errors import SearchCredentialError
from .models import CandidateCategory, CoverSearchRequest, SearchCandidate, SearchKind, SearchResponse

BASE_URL = "https://www.googleapis.com/books/v1/volumes"
_IMAGE_PRIORITIES = ("extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail")


class GoogleBooksProvider:
    def __init__(self, http_client, api_key: str = "") -> None:
        self.http = http_client
        self.api_key = str(api_key).strip()

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        if not self.api_key:
            raise SearchCredentialError(
                "Google Books 需要 Google API Key；未設定時已跳過此來源。"
            )
        if request.isbn.strip():
            query = f"isbn:{request.isbn.strip()}"
        else:
            parts = []
            if request.title.strip():
                parts.append(f"intitle:{request.title.strip()}")
            if request.author.strip():
                parts.append(f"inauthor:{request.author.strip()}")
            query = " ".join(parts) or request.query.strip()
        params = {
            "q": query,
            "maxResults": min(request.max_results, 40),
            "langRestrict": request.locale.split("-")[0],
            "key": self.api_key,
        }
        payload = self.http.get_json(BASE_URL, params)
        candidates: list[SearchCandidate] = []
        for item in payload.get("items", []) if isinstance(payload.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            info = item.get("volumeInfo")
            if not isinstance(info, dict):
                continue
            links = info.get("imageLinks")
            if not isinstance(links, dict):
                continue
            image_url = next((str(links[key]) for key in _IMAGE_PRIORITIES if links.get(key)), "")
            image_url = _google_https(image_url)
            if not image_url:
                continue
            preview_url = _google_https(str(links.get("thumbnail") or links.get("smallThumbnail") or image_url))
            source = str(info.get("infoLink") or info.get("canonicalVolumeLink") or "")
            source = _google_https(source)
            if not source:
                continue
            authors = info.get("authors") if isinstance(info.get("authors"), list) else []
            industry = info.get("industryIdentifiers") if isinstance(info.get("industryIdentifiers"), list) else []
            isbn = ""
            for identifier in industry:
                if isinstance(identifier, dict) and identifier.get("identifier"):
                    isbn = str(identifier["identifier"])
                    if str(identifier.get("type", "")).upper() == "ISBN_13":
                        break
            candidates.append(
                SearchCandidate(
                    provider="google_books",
                    candidate_id=str(item.get("id", image_url)),
                    query_kind=SearchKind.FRONT,
                    proposed_category=CandidateCategory.FRONT,
                    title=str(info.get("title", "")),
                    author=", ".join(str(value) for value in authors),
                    isbn=isbn,
                    preview_url=preview_url,
                    image_url=image_url,
                    source_page=source,
                    language=str(info.get("language", "")),
                    publisher=str(info.get("publisher", "")),
                    media_type="image/jpeg",
                    rights=str(info.get("rights", "")),
                    classification_confidence=0.95,
                    classification_reasons=("公開書庫封面",),
                )
            )
        return SearchResponse(tuple(candidates))


def _google_https(value: str) -> str:
    if value.startswith("http://"):
        value = "https://" + value[len("http://") :]
    return _https_or_empty(value)


def _https_or_empty(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme.casefold() != "https":
        return ""
    return urlunsplit(parsed)
