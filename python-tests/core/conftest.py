from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from PIL import Image


@pytest.fixture()
def sample_epub(tmp_path: Path) -> Path:
    path = tmp_path / "sample.epub"
    image_data = BytesIO()
    Image.new("RGB", (240, 360), "white").save(image_data, format="PNG")

    container_xml = """<?xml version='1.0'?>
    <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
      <rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>
    </container>"""
    opf = """<?xml version='1.0' encoding='utf-8'?>
    <package xmlns='http://www.idpf.org/2007/opf' version='2.0' unique-identifier='id'>
      <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>
        <dc:title>測試小說</dc:title><dc:creator>測試作者</dc:creator><dc:language>zh-TW</dc:language>
      </metadata>
      <manifest>
        <item id='c1' href='Text/chapter1.xhtml' media-type='application/xhtml+xml'/>
        <item id='c2' href='Text/chapter2.xhtml' media-type='application/xhtml+xml'/>
        <item id='pic' href='Images/pic.png' media-type='image/png'/>
      </manifest>
      <spine><itemref idref='c2'/><itemref idref='c1'/></spine>
    </package>"""
    chapter2 = """<html xmlns='http://www.w3.org/1999/xhtml'><body><div class='chapter'>
      <h1>第二章</h1>
      <p>先出現的段落，包含 <strong>粗體</strong> 和 <em>斜體</em>。</p>
      <p><img src='../Images/pic.png' alt='插圖'/></p>
      <p>圖片後面的段落。</p>
    </div></body></html>"""
    chapter1 = """<html xmlns='http://www.w3.org/1999/xhtml'><body>
      <h1>第一章</h1><p>後出現的段落。</p>
    </body></html>"""

    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
        zf.writestr("OEBPS/Text/chapter1.xhtml", chapter1, compress_type=ZIP_DEFLATED)
        zf.writestr("OEBPS/Text/chapter2.xhtml", chapter2, compress_type=ZIP_DEFLATED)
        zf.writestr("OEBPS/Images/pic.png", image_data.getvalue(), compress_type=ZIP_DEFLATED)
    return path
