"""Provider-neutral cover image search contracts, providers, and transport."""

from .aggregate import PublicBookSearch
from .errors import (
    CoverSearchError,
    ImageDownloadError,
    SearchCredentialError,
    SearchQuotaError,
    SearchResponseError,
    SearchTimeoutError,
    SearchTransportError,
)
from .google_books import GoogleBooksProvider
from .http import DownloadTransportResult, JsonHttpClient
from .models import (
    CandidateCategory,
    CandidateClassification,
    CoverSearchRequest,
    ProviderCredential,
    SearchCandidate,
    SearchKind,
    SearchResponse,
)
from .open_library import OpenLibraryProvider

__all__ = [
    "CandidateCategory",
    "CandidateClassification",
    "CoverSearchError",
    "CoverSearchRequest",
    "DownloadTransportResult",
    "GoogleBooksProvider",
    "ImageDownloadError",
    "JsonHttpClient",
    "OpenLibraryProvider",
    "ProviderCredential",
    "PublicBookSearch",
    "SearchCandidate",
    "SearchCredentialError",
    "SearchKind",
    "SearchQuotaError",
    "SearchResponse",
    "SearchResponseError",
    "SearchTimeoutError",
    "SearchTransportError",
]
