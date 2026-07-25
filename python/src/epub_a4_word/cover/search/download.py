from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .errors import ImageDownloadError
from .models import SearchCandidate

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/tiff",
    "image/bmp",
}


@dataclass(frozen=True)
class DownloadedImage:
    path: Path
    content_type: str
    byte_count: int
    width: int
    height: int
    sha256: str


def download_candidate(
    candidate: SearchCandidate,
    destination: Path | str,
    http_client,
) -> DownloadedImage:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        transport = http_client.stream_download(
            candidate.image_url,
            temporary,
            MAX_DOWNLOAD_BYTES,
        )
        content_type = transport.content_type.split(";", 1)[0].strip().casefold()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ImageDownloadError("下載內容不是支援的圖片格式。")
        try:
            with Image.open(temporary) as image:
                image.verify()
            with Image.open(temporary) as image:
                image.load()
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageDownloadError("下載內容不是可用圖片。") from exc
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ImageDownloadError("圖片尺寸超過 20,000 × 20,000 像素限制。")
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, output)
        return DownloadedImage(
            path=output.resolve(),
            content_type=content_type,
            byte_count=transport.byte_count,
            width=width,
            height=height,
            sha256=digest,
        )
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
