from __future__ import annotations

import threading
import time

from .models import CandidateCategory, CoverSearchRequest, SearchCandidate, SearchKind, SearchResponse

BASE_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_USER_AGENT = (
    "EPUB2A4-CoverTool/0.7 "
    "(+https://github.com/eightkingdomsalliedforces-hash/epub2a4)"
)


class OpenLibraryProvider:
    def __init__(self, http_client, min_interval_seconds: float = 1.05) -> None:
        self.http = http_client
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._last_request_at = 0.0
        self._rate_lock = threading.Lock()

    def _wait_for_rate_limit(self) -> None:
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
            self._last_request_at = time.monotonic()

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
        self._wait_for_rate_limit()
        payload = self.http.get_json(
            BASE_URL,
            params,
            headers={"User-Agent": OPEN_LIBRARY_USER_AGENT, "Accept": "application/json"},
        )
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
