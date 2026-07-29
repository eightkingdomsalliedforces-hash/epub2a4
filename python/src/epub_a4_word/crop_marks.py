from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from docx.oxml import parse_xml

from .docx_compat import install_story_template_fallbacks
from .page_placement import CropGuide

PT_PER_MM = 72.0 / 25.4
EMU_PER_MM = 36000
EMU_PER_PT = 12700
_GUIDE_IDENTIFIER_RE = re.compile(
    r"epub2a4-(?:guide|(?:crop|fold)-guide)-(\d+)"
)


@dataclass(frozen=True)
class CropMarkFrame:
    """Compatibility frame for callers that still request corner crop marks."""

    page_width_cm: float
    page_height_cm: float
    left_cm: float
    top_cm: float
    width_cm: float
    height_cm: float

    @property
    def right_cm(self) -> float:
        return self.left_cm + self.width_cm

    @property
    def bottom_cm(self) -> float:
        return self.top_cm + self.height_cm


def _pt(mm: float) -> float:
    return float(mm) * PT_PER_MM


def _line_xml(identifier: int, guide: CropGuide, stroke_pt: float) -> str:
    dash = '<v:stroke dashstyle="dash" />' if guide.role == "fold" else ""
    return (
        '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office">'
        f'<v:line id="epub2a4-guide-{identifier}" '
        'style="position:absolute;z-index:251659264;'
        'mso-position-horizontal-relative:page;mso-position-vertical-relative:page;'
        'mso-layout-in-cell:f" '
        f'from="{_pt(guide.x1_mm):.3f}pt,{_pt(guide.y1_mm):.3f}pt" '
        f'to="{_pt(guide.x2_mm):.3f}pt,{_pt(guide.y2_mm):.3f}pt" '
        f'strokecolor="#000000" strokeweight="{stroke_pt:.2f}pt">'
        f'{dash}<o:lock v:ext="edit" rotation="t" />'
        '</v:line></w:pict>'
    )


def _drawing_line_xml(identifier: int, guide: CropGuide, stroke_pt: float) -> str:
    x = round(min(guide.x1_mm, guide.x2_mm) * EMU_PER_MM)
    y = round(min(guide.y1_mm, guide.y2_mm) * EMU_PER_MM)
    cx = max(1, round(abs(guide.x2_mm - guide.x1_mm) * EMU_PER_MM))
    cy = max(1, round(abs(guide.y2_mm - guide.y1_mm) * EMU_PER_MM))
    flip_h = ' flipH="1"' if guide.x2_mm < guide.x1_mm else ""
    flip_v = ' flipV="1"' if guide.y2_mm < guide.y1_mm else ""
    dash = '<a:prstDash val="dash" />' if guide.role == "fold" else ""
    stroke_emu = max(1, round(float(stroke_pt) * EMU_PER_PT))
    name = f"epub2a4-{guide.role}-guide-{identifier}"
    return (
        '<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" '
        'relativeHeight="251659264" behindDoc="0" locked="1" layoutInCell="0" allowOverlap="1">'
        '<wp:simplePos x="0" y="0" />'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>{x}</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="page"><wp:posOffset>{y}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="{cx}" cy="{cy}" />'
        '<wp:effectExtent l="0" t="0" r="0" b="0" />'
        '<wp:wrapNone />'
        f'<wp:docPr id="{identifier}" name="{name}" />'
        '<wp:cNvGraphicFramePr />'
        '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<wps:wsp><wps:cNvSpPr /><wps:spPr>'
        f'<a:xfrm{flip_h}{flip_v}><a:off x="0" y="0" /><a:ext cx="{cx}" cy="{cy}" /></a:xfrm>'
        '<a:prstGeom prst="line"><a:avLst /></a:prstGeom>'
        f'<a:ln w="{stroke_emu}"><a:solidFill><a:srgbClr val="000000" /></a:solidFill>{dash}'
        '<a:headEnd type="none" w="med" len="med" /><a:tailEnd type="none" w="med" len="med" />'
        '</a:ln></wps:spPr><wps:bodyPr /></wps:wsp>'
        '</a:graphicData></a:graphic>'
        '</wp:anchor></w:drawing>'
    )


def add_guides_to_paragraph(
    paragraph,
    guides: Sequence[CropGuide],
    *,
    paper_width_mm: float,
    paper_height_mm: float,
    stroke_pt: float = 0.35,
    render_mode: str = "vml",
    identifier_start: int | None = None,
) -> None:
    """Draw page-relative crop or fold guides in a paragraph."""

    if identifier_start is not None and identifier_start < 1:
        raise ValueError("identifier_start must be positive")
    if stroke_pt <= 0.0:
        raise ValueError("導線寬度必須大於 0。")
    if render_mode not in {"vml", "drawingml"}:
        raise ValueError("導線渲染模式必須是 vml 或 drawingml。")
    for guide in guides:
        if guide.role not in {"crop", "fold"}:
            raise ValueError(f"未知導線角色：{guide.role}")
        if min(guide.x1_mm, guide.x2_mm) < 0.0 or max(
            guide.x1_mm, guide.x2_mm
        ) > paper_width_mm:
            raise ValueError("導線超出紙張水平範圍。")
        if min(guide.y1_mm, guide.y2_mm) < 0.0 or max(
            guide.y1_mm, guide.y2_mm
        ) > paper_height_mm:
            raise ValueError("導線超出紙張垂直範圍。")

    if not guides:
        return
    install_story_template_fallbacks()
    if identifier_start is None:
        existing_identifiers = [
            int(match)
            for match in _GUIDE_IDENTIFIER_RE.findall(
                paragraph.part.element.xml
            )
        ]
        first_identifier = max(
            paragraph.part.next_id,
            max(existing_identifiers, default=0) + 1,
        )
    else:
        first_identifier = identifier_start
    for index, guide in enumerate(guides, start=first_identifier):
        run = paragraph.add_run()
        xml = (
            _drawing_line_xml(index, guide, stroke_pt)
            if render_mode == "drawingml"
            else _line_xml(index, guide, stroke_pt)
        )
        run._r.append(parse_xml(xml))


def add_page_guides(
    section,
    guides: Sequence[CropGuide],
    *,
    paper_width_mm: float,
    paper_height_mm: float,
    stroke_pt: float = 0.35,
    render_mode: str = "vml",
) -> None:
    """Draw page-relative crop or fold guides in the repeating header."""

    if not guides:
        return
    header = section.header
    header.is_linked_to_previous = False
    paragraph = header.paragraphs[0]
    paragraph.paragraph_format.space_before = 0
    paragraph.paragraph_format.space_after = 0
    paragraph.paragraph_format.line_spacing = 1
    add_guides_to_paragraph(
        paragraph,
        guides,
        paper_width_mm=paper_width_mm,
        paper_height_mm=paper_height_mm,
        stroke_pt=stroke_pt,
        render_mode=render_mode,
    )


def add_crop_marks(
    section,
    frame: CropMarkFrame,
    *,
    length_mm: float = 5.0,
    gap_mm: float = 2.0,
) -> None:
    """Compatibility wrapper that draws the historical eight corner marks."""

    if length_mm <= 0.0 or gap_mm < 0.0:
        raise ValueError("裁切標記長度與間距無效。")
    left = frame.left_cm * 10.0
    right = frame.right_cm * 10.0
    top = frame.top_cm * 10.0
    bottom = frame.bottom_cm * 10.0
    length = float(length_mm)
    gap = float(gap_mm)
    guides = (
        CropGuide(left - gap - length, top, left - gap, top),
        CropGuide(left, top - gap - length, left, top - gap),
        CropGuide(right + gap, top, right + gap + length, top),
        CropGuide(right, top - gap - length, right, top - gap),
        CropGuide(left - gap - length, bottom, left - gap, bottom),
        CropGuide(left, bottom + gap, left, bottom + gap + length),
        CropGuide(right + gap, bottom, right + gap + length, bottom),
        CropGuide(right, bottom + gap, right, bottom + gap + length),
    )
    add_page_guides(
        section,
        guides,
        paper_width_mm=frame.page_width_cm * 10.0,
        paper_height_mm=frame.page_height_cm * 10.0,
        stroke_pt=0.5,
    )
