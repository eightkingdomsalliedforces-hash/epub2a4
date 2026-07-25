from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

SENSITIVE_KEYS = {"key", "api_key", "cx", "search_engine_id"}


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    return {
        key: "<redacted>" if key.casefold() in SENSITIVE_KEYS else value
        for key, value in values.items()
    }


def safe_request_description(url: str, params: Mapping[str, object]) -> str:
    parsed = urlsplit(url)
    clean = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return f"GET {clean} params={redact_mapping(params)!r}"


class CoverSearchError(RuntimeError):
    """Base error for cover search and remote-image handling."""


class SearchTransportError(CoverSearchError):
    def __init__(
        self,
        message: str,
        *,
        url: str = "",
        params: Mapping[str, object] | None = None,
    ) -> None:
        detail = ""
        if url:
            detail = "; " + safe_request_description(url, params or {})
        super().__init__(message + detail)


class SearchCredentialError(CoverSearchError):
    pass


class SearchQuotaError(CoverSearchError):
    pass


class SearchTimeoutError(CoverSearchError):
    pass


class NoSearchResultsError(CoverSearchError):
    pass


class ImageDownloadError(CoverSearchError):
    pass
