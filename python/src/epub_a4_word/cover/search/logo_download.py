from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
from pathlib import Path
import re
from typing import Callable
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError

from .errors import ImageDownloadError
from .logo_http import LogoHttpClient
from .logo_models import LogoCandidate

MAX_LOGO_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000
SvgConverter = Callable[[bytes, int, int], bytes]


@dataclass(frozen=True)
class DownloadedLogo:
    path: Path
    source_url: str
    content_type: str
    byte_count: int
    image_format: str
    width_px: int
    height_px: int
    transparent_background: bool | None
    sha256: str


def _svg_dimension(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", value)
    return max(1, round(float(match.group(1)))) if match else None


def _validate_svg(data: bytes) -> tuple[int, int]:
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise ImageDownloadError("SVG 格式無效。") from exc
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].casefold()
        if tag in {"script", "foreignobject", "iframe", "object", "embed"}:
            raise ImageDownloadError("SVG 含有不允許的主動內容。")
        for name, value in element.attrib.items():
            attr = name.rsplit("}", 1)[-1].casefold()
            text = str(value).strip()
            if attr.startswith("on"):
                raise ImageDownloadError("SVG 含有不允許的事件處理程式。")
            if attr in {"href", "src"} and text and not text.startswith("#"):
                raise ImageDownloadError("SVG 含有外部資源。")
            if "url(" in text.casefold() and "url(#" not in text.casefold():
                raise ImageDownloadError("SVG 含有外部資源。")
    width = _svg_dimension(root.attrib.get("width"))
    height = _svg_dimension(root.attrib.get("height"))
    if width is None or height is None:
        view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
        if view_box:
            values = re.split(r"[ ,]+", view_box.strip())
            if len(values) == 4:
                try:
                    width = max(1, round(float(values[2])))
                    height = max(1, round(float(values[3])))
                except ValueError:
                    pass
    return width or 1, height or 1


def _validate_raster(data: bytes) -> tuple[str, int, int, bool | None]:
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            image_format = str(image.format or "").upper()
            width, height = image.size
            transparent: bool | None = None
            if "A" in image.getbands():
                alpha = image.getchannel("A")
                transparent = alpha.getextrema()[0] < 255
            elif "transparency" in image.info:
                transparent = True
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageDownloadError("下載內容不是可用 Logo 圖片。") from exc
    return image_format, width, height, transparent


def download_logo(
    candidate: LogoCandidate,
    destination_dir: Path | str,
    *,
    http=None,
    svg_converter: SvgConverter | None = None,
) -> DownloadedLogo:
    client = http or LogoHttpClient()
    data, content_type, final_url = client.download_bytes(
        candidate.image_url,
        max_bytes=MAX_LOGO_BYTES,
    )
    normalized_type = str(content_type).split(";", 1)[0].strip().casefold()
    is_svg = normalized_type == "image/svg+xml" or data.lstrip().startswith(b"<svg")
    if is_svg:
        width, height = _validate_svg(data)
        if svg_converter is None:
            image_format = "SVG"
            transparent = True
            suffix = ".svg"
            normalized_type = "image/svg+xml"
        else:
            try:
                data = svg_converter(data, width, height)
            except ImageDownloadError:
                raise
            except Exception as exc:
                raise ImageDownloadError("SVG Logo 轉換為 PNG 失敗。") from exc
            image_format, width, height, transparent = _validate_raster(data)
            if image_format != "PNG":
                raise ImageDownloadError("SVG Logo 轉換器必須輸出 PNG。")
            suffix = ".png"
            normalized_type = "image/png"
    else:
        image_format, width, height, transparent = _validate_raster(data)
        suffix = {
            "PNG": ".png",
            "JPEG": ".jpg",
            "WEBP": ".webp",
            "GIF": ".gif",
            "TIFF": ".tiff",
            "BMP": ".bmp",
        }.get(image_format)
        if suffix is None:
            raise ImageDownloadError("下載內容不是支援的 Logo 圖片格式。")
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ImageDownloadError("Logo 尺寸超過 20,000 × 20,000 像素限制。")
    digest = hashlib.sha256(data).hexdigest()
    root = Path(destination_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = root / f"{digest}{suffix}"
    if not output.exists():
        temporary = output.with_suffix(output.suffix + ".part")
        temporary.write_bytes(data)
        temporary.replace(output)
    return DownloadedLogo(
        path=output,
        source_url=final_url,
        content_type=normalized_type,
        byte_count=len(data),
        image_format=image_format,
        width_px=width,
        height_px=height,
        transparent_background=transparent,
        sha256=digest,
    )


def import_logo_file(
    source_path: Path | str,
    destination_dir: Path | str,
    *,
    svg_converter: SvgConverter | None = None,
) -> DownloadedLogo:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ImageDownloadError(f"找不到 Logo 圖片：{source}")
    data = source.read_bytes()
    if len(data) > MAX_LOGO_BYTES:
        raise ImageDownloadError("Logo 超過 10 MiB 限制。")
    candidate = LogoCandidate(
        provider="manual",
        candidate_id=hashlib.sha256(data).hexdigest()[:16],
        title=source.stem,
        image_url="https://manual.local/logo",
        preview_url="https://manual.local/logo",
        source_page="https://manual.local/",
        source_category="manual",
        source_domain="manual.local",
        media_type="image/svg+xml" if source.suffix.casefold() == ".svg" else "",
    )

    class _LocalClient:
        def download_bytes(self, _url: str, *, max_bytes: int):
            if len(data) > max_bytes:
                raise ImageDownloadError("Logo 超過 10 MiB 限制。")
            return data, candidate.media_type or "application/octet-stream", str(source)

    return download_logo(
        candidate,
        destination_dir,
        http=_LocalClient(),
        svg_converter=svg_converter,
    )
