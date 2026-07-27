from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from epub_a4_word.cover.search.errors import ImageDownloadError
from epub_a4_word.cover.search.logo_cache import LogoCache
from epub_a4_word.cover.search.logo_download import MAX_LOGO_BYTES, download_logo
from epub_a4_word.cover.search.logo_models import LogoCandidate, LogoSourceCategory


def _candidate(url: str, media_type: str = "image/png") -> LogoCandidate:
    return LogoCandidate(
        provider="test",
        candidate_id="logo",
        title="Logo",
        image_url=url,
        preview_url=url,
        source_page="https://example.test/source",
        source_category=LogoSourceCategory.OTHER,
        source_domain="example.test",
        media_type=media_type,
    )


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (64, 24), (255, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeBinaryClient:
    def __init__(self, data: bytes, content_type: str) -> None:
        self.data = data
        self.content_type = content_type
        self.max_bytes: int | None = None

    def download_bytes(self, url: str, *, max_bytes: int):
        self.max_bytes = max_bytes
        if len(self.data) > max_bytes:
            raise ImageDownloadError("too large")
        return self.data, self.content_type, url


def test_download_logo_validates_png_and_records_transparency(tmp_path: Path) -> None:
    client = FakeBinaryClient(_png_bytes(), "image/png")

    downloaded = download_logo(
        _candidate("https://example.test/logo.png"),
        tmp_path,
        http=client,
    )

    assert client.max_bytes == MAX_LOGO_BYTES
    assert downloaded.path.is_file()
    assert downloaded.image_format == "PNG"
    assert (downloaded.width_px, downloaded.height_px) == (64, 24)
    assert downloaded.transparent_background is True
    assert downloaded.sha256


def test_download_logo_rejects_active_svg(tmp_path: Path) -> None:
    active = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    client = FakeBinaryClient(active, "image/svg+xml")

    with pytest.raises(ImageDownloadError, match="SVG"):
        download_logo(
            _candidate("https://example.test/logo.svg", "image/svg+xml"),
            tmp_path,
            http=client,
        )


def test_logo_cache_reuses_downloaded_file_offline(tmp_path: Path) -> None:
    downloaded = download_logo(
        _candidate("https://example.test/logo.png"),
        tmp_path / "download",
        http=FakeBinaryClient(_png_bytes(), "image/png"),
    )
    cache = LogoCache(tmp_path / "cache", max_bytes=1024 * 1024)

    cached = cache.put("https://example.test/logo.png", downloaded)
    reopened = LogoCache(tmp_path / "cache", max_bytes=1024 * 1024)

    assert cached.is_file()
    assert reopened.get("https://example.test/logo.png") == cached
