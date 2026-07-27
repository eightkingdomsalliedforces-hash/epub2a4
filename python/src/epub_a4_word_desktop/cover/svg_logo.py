from __future__ import annotations

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from epub_a4_word.cover.search.errors import ImageDownloadError

_MAX_RASTER_EDGE = 2048


def rasterize_svg_logo(data: bytes, width: int, height: int) -> bytes:
    """Rasterize an already validated SVG to a transparent PNG for project storage."""

    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise ImageDownloadError("SVG Logo 無法由 Qt 解析。")

    source_width = max(1, int(width))
    source_height = max(1, int(height))
    if source_width >= source_height:
        output_width = _MAX_RASTER_EDGE
        output_height = max(1, round(_MAX_RASTER_EDGE * source_height / source_width))
    else:
        output_height = _MAX_RASTER_EDGE
        output_width = max(1, round(_MAX_RASTER_EDGE * source_width / source_height))

    image = QImage(
        output_width,
        output_height,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ImageDownloadError("無法建立 SVG Logo 的 PNG 緩衝區。")
    try:
        if not image.save(buffer, "PNG"):
            raise ImageDownloadError("無法將 SVG Logo 儲存為 PNG。")
    finally:
        buffer.close()
    return bytes(payload)
