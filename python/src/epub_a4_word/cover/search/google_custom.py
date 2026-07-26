from __future__ import annotations

from .classifier import classify_candidate
from .errors import SearchCredentialError
from .models import (
    CandidateCategory,
    CoverSearchRequest,
    ProviderCredential,
    SearchCandidate,
    SearchResponse,
)

BASE_URL = "https://customsearch.googleapis.com/customsearch/v1"


class GoogleCustomSearchProvider:
    def __init__(self, http_client) -> None:
        self.http = http_client

    def search(
        self,
        request: CoverSearchRequest,
        credential: ProviderCredential | None,
    ) -> SearchResponse:
        if (
            credential is None
            or not credential.api_key.strip()
            or not credential.search_engine_id.strip()
        ):
            raise SearchCredentialError("請先輸入 API Key 與 Search Engine ID。")
        params = {
            "key": credential.api_key,
            "cx": credential.search_engine_id,
            "q": request.query,
            "searchType": "image",
            "num": min(request.max_results, 10),
            "safe": "active" if request.safe_search else "off",
            "hl": request.locale,
        }
        payload = self.http.get_json(BASE_URL, params)
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        candidates: list[SearchCandidate] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            image = item.get("image") if isinstance(item.get("image"), dict) else {}
            image_url = str(item.get("link") or "")
            preview = str(image.get("thumbnailLink") or image_url)
            source = str(image.get("contextLink") or "")
            if not all(url.startswith("https://") for url in (image_url, preview, source)):
                continue
            candidate = SearchCandidate(
                provider="google_custom",
                candidate_id=str(item.get("cacheId") or f"{request.kind.value}-{index}-{image_url}"),
                query_kind=request.kind,
                proposed_category=CandidateCategory(request.kind.value),
                title=str(item.get("title", "")),
                author="",
                isbn=request.isbn,
                preview_url=preview,
                image_url=image_url,
                source_page=source,
                width_px=_optional_int(image.get("width")),
                height_px=_optional_int(image.get("height")),
                media_type=str(item.get("mime", "")),
                rights="",
            )
            candidates.append(candidate.with_classification(classify_candidate(candidate, request.kind)))
        return SearchResponse(tuple(candidates))


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
