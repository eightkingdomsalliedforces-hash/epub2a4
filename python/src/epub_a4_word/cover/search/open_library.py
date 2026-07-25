from __future__ import annotations

from .models import CandidateCategory, CoverSearchRequest, SearchCandidate, SearchKind, SearchResponse

BASE_URL = "https://openlibrary.org/search.json"


class OpenLibraryProvider:
    def __init__(self, http_client) -> None:
        self.http = http_client

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        params: dict[str, object] = {
            "fields": "key,title,author_name,isbn,cover_i,edition_key",
            "limit": min(request.max_results, 40),
        }
        if request.isbn.strip():
            params["isbn"] = request.isbn.strip()
        else:
            if request.title.strip():
                params["title"] = request.title.strip()
            if request.author.strip():
                params["author"] = request.author.strip()
            if not request.title.strip() and request.query.strip():
                params["q"] = request.query.strip()
        payload = self.http.get_json(BASE_URL, params)
        docs = payload.get("docs") if isinstance(payload.get("docs"), list) else []
        candidates: list[SearchCandidate] = []
        for item in docs:
            if not isinstance(item, dict) or not item.get("cover_i"):
                continue
            cover_id = int(item["cover_i"])
            key = str(item.get("key") or "")
            if not key.startswith("/"):
                continue
            authors = item.get("author_name") if isinstance(item.get("author_name"), list) else []
            isbns = item.get("isbn") if isinstance(item.get("isbn"), list) else []
            candidates.append(
                SearchCandidate(
                    provider="open_library",
                    candidate_id=key,
                    query_kind=SearchKind.FRONT,
                    proposed_category=CandidateCategory.FRONT,
                    title=str(item.get("title", "")),
                    author=", ".join(str(value) for value in authors),
                    isbn=str(isbns[0]) if isbns else "",
                    preview_url=f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
                    image_url=f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg",
                    source_page=f"https://openlibrary.org{key}",
                    media_type="image/jpeg",
                    classification_confidence=0.95,
                    classification_reasons=("公開書庫封面",),
                )
            )
        return SearchResponse(tuple(candidates))
