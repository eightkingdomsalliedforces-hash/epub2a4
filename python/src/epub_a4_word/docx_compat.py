from __future__ import annotations

from pathlib import Path
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


def _template_exists(filename: str) -> bool:
    module_path = Path(str(hdrftr.__file__))
    return (module_path.parent.parent / "templates" / filename).is_file()


def install_story_template_fallbacks(*, force: bool = False) -> bool:
    """Use inline header/footer XML when python-docx package data is absent.

    Chaquopy can install the python-docx modules while omitting the standalone
    ``docx/templates/default-header.xml`` and ``default-footer.xml`` resources.
    Accessing ``section.header`` or ``section.footer`` then raises
    ``FileNotFoundError``. The fallback keeps python-docx's normal behavior on
    desktop and replaces only the missing resource loaders on affected builds.
    """

    global _INSTALLED
    if _INSTALLED and not force:
        return False

    changed = False
    if force or not _template_exists("default-header.xml"):
        HeaderPart._default_header_xml = classmethod(lambda cls: _HEADER_XML)
        changed = True
    if force or not _template_exists("default-footer.xml"):
        FooterPart._default_footer_xml = classmethod(lambda cls: _FOOTER_XML)
        changed = True
    _INSTALLED = True
    return changed
