from __future__ import annotations

import os
from typing import Final

from docx.parts import hdrftr
from docx.parts.hdrftr import FooterPart, HeaderPart

_W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_HEADER_XML: Final = (
    "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
    f'<w:hdr xmlns:w="{_W_NS}">'
    '<w:p><w:pPr><w:pStyle w:val="Header"/></w:pPr></w:p>'
    "</w:hdr>"
).encode("utf-8")
_FOOTER_XML: Final = (
    "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
    f'<w:ftr xmlns:w="{_W_NS}">'
    '<w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr></w:p>'
    "</w:ftr>"
).encode("utf-8")
_INSTALLED = False


def _python_docx_template_path(filename: str) -> str:
    """Return the exact path python-docx 1.1.x attempts to open."""

    return os.path.join(
        os.path.split(str(hdrftr.__file__))[0],
        "..",
        "templates",
        filename,
    )


def _template_loader_works(filename: str) -> bool:
    """Test the real python-docx loader path rather than an equivalent path.

    Chaquopy can report the normalized archive member as present while failing
    to open python-docx's literal ``parts/../templates`` AssetFinder path.
    """

    try:
        with open(_python_docx_template_path(filename), "rb") as stream:
            stream.read(1)
    except (OSError, TypeError, ValueError):
        return False
    return True


def install_story_template_fallbacks(*, force: bool = False) -> bool:
    """Use inline header/footer XML when python-docx cannot open its templates."""

    global _INSTALLED
    if _INSTALLED and not force:
        return False

    changed = False
    if force or not _template_loader_works("default-header.xml"):
        HeaderPart._default_header_xml = classmethod(lambda cls: _HEADER_XML)
        changed = True
    if force or not _template_loader_works("default-footer.xml"):
        FooterPart._default_footer_xml = classmethod(lambda cls: _FOOTER_XML)
        changed = True
    _INSTALLED = True
    return changed


# Install before Android dispatches EPUB or DOCX conversion. Desktop builds keep
# python-docx's original loader whenever the exact filesystem access succeeds.
install_story_template_fallbacks()
