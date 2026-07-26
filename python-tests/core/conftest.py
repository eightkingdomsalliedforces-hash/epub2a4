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


@pytest.fixture()
def cover_epub_factory(tmp_path: Path):
    """Build EPUBs with explicit or medium-confidence front/back cover pages."""

    def build(*, generic_back: bool = False) -> Path:
        path = tmp_path / ("candidate-cover.epub" if generic_back else "front-back-cover.epub")
        image_data = BytesIO()
        Image.new("RGB", (600, 900), "white").save(image_data, format="PNG")
        png = image_data.getvalue()

        back_id = "plate-page" if generic_back else "back-cover-page"
        back_href = "plate.xhtml" if generic_back else "back-cover.xhtml"
        guide = "" if generic_back else "<guide><reference type='back-cover' href='Text/back-cover.xhtml'/></guide>"
        container_xml = """<?xml version='1.0'?>
        <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
          <rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>
        </container>"""
        opf = f"""<?xml version='1.0' encoding='utf-8'?>
        <package xmlns='http://www.idpf.org/2007/opf' xmlns:dc='http://purl.org/dc/elements/1.1/' version='3.0'>
          <metadata><dc:title>封面過濾測試</dc:title><dc:creator>測試作者</dc:creator></metadata>
          <manifest>
            <item id='front-page' href='Text/front.xhtml' media-type='application/xhtml+xml'/>
            <item id='chapter' href='Text/chapter.xhtml' media-type='application/xhtml+xml'/>
            <item id='{back_id}' href='Text/{back_href}' media-type='application/xhtml+xml'/>
            <item id='front-image' href='Images/front.png' media-type='image/png' properties='cover-image'/>
            <item id='back-image' href='Images/back.png' media-type='image/png'/>
          </manifest>
          <spine><itemref idref='front-page'/><itemref idref='chapter'/><itemref idref='{back_id}'/></spine>
          {guide}
        </package>"""
        front = "<html xmlns='http://www.w3.org/1999/xhtml'><body><img alt='封面' src='../Images/front.png'/></body></html>"
        chapter = "<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>第一章</h1><p>唯一正文內容。</p></body></html>"
        back = "<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='../Images/back.png'/></body></html>"
        with ZipFile(path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
            zf.writestr("META-INF/container.xml", container_xml, compress_type=ZIP_DEFLATED)
            zf.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
            zf.writestr("OEBPS/Text/front.xhtml", front, compress_type=ZIP_DEFLATED)
            zf.writestr("OEBPS/Text/chapter.xhtml", chapter, compress_type=ZIP_DEFLATED)
            zf.writestr(f"OEBPS/Text/{back_href}", back, compress_type=ZIP_DEFLATED)
            zf.writestr("OEBPS/Images/front.png", png, compress_type=ZIP_DEFLATED)
            zf.writestr("OEBPS/Images/back.png", png, compress_type=ZIP_DEFLATED)
        return path

    return build
