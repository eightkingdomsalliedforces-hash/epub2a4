"""Provider-neutral cover image search contracts and transport helpers."""

from .errors import (
    CoverSearchError,
    ImageDownloadError,
    SearchCredentialError,
    SearchQuotaError,
    SearchResponseError,
    SearchTimeoutError,
    SearchTransportError,
)
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

__all__ = [
    "CandidateCategory",
    "CandidateClassification",
    "CoverSearchError",
    "CoverSearchRequest",
    "DownloadTransportResult",
    "ImageDownloadError",
    "JsonHttpClient",
    "ProviderCredential",
    "SearchCandidate",
    "SearchCredentialError",
    "SearchKind",
    "SearchQuotaError",
    "SearchResponse",
    "SearchResponseError",
    "SearchTimeoutError",
    "SearchTransportError",
]
