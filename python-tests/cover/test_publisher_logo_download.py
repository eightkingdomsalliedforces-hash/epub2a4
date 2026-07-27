from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from epub_a4_word.cover.search.errors import ImageDownloadError
from epub_a4_word.cover.search.logo_cache import LogoCache
from epub_a4_word.cover.search.logo_download import (
    MAX_LOGO_BYTES,
    download_logo,
    import_logo_file,
)
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


def test_manual_png_import_accepts_svg_converter_without_calling_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "logo.png"
    source.write_bytes(_png_bytes())

    def unexpected_converter(_data: bytes, _width: int, _height: int) -> bytes:
        raise AssertionError("PNG must not invoke the SVG converter")

    downloaded = import_logo_file(
        source,
        tmp_path / "validated",
        svg_converter=unexpected_converter,
    )

    assert downloaded.image_format == "PNG"
    assert downloaded.path.suffix == ".png"


def test_manual_svg_import_converts_validated_svg_to_png(tmp_path: Path) -> None:
    source = tmp_path / "logo.svg"
    source.write_bytes(
        b"<svg xmlns='http://www.w3.org/2000/svg' width='120' height='40'>"
        b"<rect width='120' height='40' fill='#f15a24'/></svg>"
    )
    calls: list[tuple[int, int]] = []

    def converter(_data: bytes, width: int, height: int) -> bytes:
        calls.append((width, height))
        return _png_bytes()

    downloaded = import_logo_file(
        source,
        tmp_path / "validated",
        svg_converter=converter,
    )

    assert calls == [(120, 40)]
    assert downloaded.image_format == "PNG"
    assert downloaded.content_type == "image/png"
    assert downloaded.path.suffix == ".png"


def test_online_svg_download_converts_validated_svg_to_png(tmp_path: Path) -> None:
    svg = (
        b"<svg xmlns='http://www.w3.org/2000/svg' width='80' height='20'>"
        b"<rect width='80' height='20' fill='black'/></svg>"
    )
    calls: list[tuple[int, int]] = []

    def converter(_data: bytes, width: int, height: int) -> bytes:
        calls.append((width, height))
        return _png_bytes()

    downloaded = download_logo(
        _candidate("https://example.test/logo.svg", "image/svg+xml"),
        tmp_path,
        http=FakeBinaryClient(svg, "image/svg+xml"),
        svg_converter=converter,
    )

    assert calls == [(80, 20)]
    assert downloaded.image_format == "PNG"
    assert downloaded.path.suffix == ".png"
