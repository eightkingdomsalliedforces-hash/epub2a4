from __future__ import annotations


class CoverSearchError(RuntimeError):
    """Base class for cover-search and selected-image failures."""


class SearchTransportError(CoverSearchError):
    """The remote service could not be reached or returned an HTTP failure."""


class SearchCredentialError(SearchTransportError):
    """The remote service rejected its configured credentials."""


class SearchQuotaError(SearchTransportError):
    """The remote service rejected the request because quota is exhausted."""


class SearchTimeoutError(SearchTransportError):
    """The remote request exceeded the configured timeout."""


class SearchResponseError(CoverSearchError):
    """The remote service returned an invalid or unsupported response."""


class ImageDownloadError(CoverSearchError):
    """A selected image could not be downloaded or validated."""
