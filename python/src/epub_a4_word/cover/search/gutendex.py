from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .models import (
    CandidateCategory,
    CoverSearchRequest,
    SearchCandidate,
    SearchKind,
    SearchResponse,
)

GUTENDEX_URL = "https://gutendex.com/books"
GUTENDEX_USER_AGENT = (
    "EPUB2A4-CoverTool/0.8 "
    "(+https://github.com/eightkingdomsalliedforces-hash/epub2a4)"
)


def _https_url(value: object) -> str:
    text = str(value or "").strip()
    parsed = urlsplit(text)
    if parsed.scheme.casefold() == "http":
        parsed = parsed._replace(scheme="https")
        return urlunsplit(parsed)
    return text if parsed.scheme.casefold() == "https" else ""


class GutendexProvider:
    name = "gutendex"

    def __init__(self, http) -> None:
        self.http = http

    def search(self, request: CoverSearchRequest) -> SearchResponse:
        if request.kind is not SearchKind.FRONT:
            return SearchResponse()
        terms = " ".join(
            part.strip()
            for part in (request.title or request.query, request.author)
            if part.strip()
        )
        if not terms:
            return SearchResponse()
        params: dict[str, object] = {"search": terms}
        language = request.locale.replace("_", "-").split("-", 1)[0].casefold()
        if language:
            params["languages"] = language
        payload = self.http.get_json(
            GUTENDEX_URL,
            params,
            headers={"User-Agent": GUTENDEX_USER_AGENT, "Accept": "application/json"},
        )
        results = payload.get("results")
        if not isinstance(results, list):
            return SearchResponse()
        candidates: list[SearchCandidate] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            formats = item.get("formats")
            if not isinstance(formats, dict):
                continue
            image_url = _https_url(formats.get("image/jpeg"))
            if not image_url:
                continue
            try:
                book_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            authors = item.get("authors")
            author_names = (
                [
                    str(author.get("name", "")).strip()
                    for author in authors
                    if isinstance(author, dict) and str(author.get("name", "")).strip()
                ]
                if isinstance(authors, list)
                else []
            )
            candidates.append(
                SearchCandidate(
                    provider=self.name,
                    candidate_id=str(book_id),
                    query_kind=SearchKind.FRONT,
                    proposed_category=CandidateCategory.FRONT,
                    title=str(item.get("title", "")).strip(),
                    author=", ".join(author_names),
                    isbn="",
                    preview_url=image_url,
                    image_url=image_url,
                    source_page=f"https://www.gutenberg.org/ebooks/{book_id}",
                    language=str(
                        (item.get("languages") or [""])[0]
                        if isinstance(item.get("languages"), list)
                        else ""
                    ),
                    media_type="image/jpeg",
                    classification_confidence=0.90,
                    classification_reasons=("Project Gutenberg 書目封面",),
                )
            )
            if len(candidates) >= request.max_results:
                break
        return SearchResponse(tuple(candidates))
