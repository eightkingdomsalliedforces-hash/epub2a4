from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from docx.oxml import parse_xml

from .docx_compat import install_story_template_fallbacks
from .page_placement import CropGuide

PT_PER_MM = 72.0 / 25.4


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
        'mso-position-horizontal-relative:page;mso-position-vertical-relative:page" '
        f'from="{_pt(guide.x1_mm):.3f}pt,{_pt(guide.y1_mm):.3f}pt" '
        f'to="{_pt(guide.x2_mm):.3f}pt,{_pt(guide.y2_mm):.3f}pt" '
        f'strokecolor="#000000" strokeweight="{stroke_pt:.2f}pt">'
        f'{dash}<o:lock v:ext="edit" rotation="t" />'
        '</v:line></w:pict>'
    )


def add_page_guides(
    section,
    guides: Sequence[CropGuide],
    *,
    paper_width_mm: float,
    paper_height_mm: float,
    stroke_pt: float = 0.35,
) -> None:
    """Draw page-relative crop or fold guides in the repeating header."""

    if stroke_pt <= 0.0:
        raise ValueError("導線寬度必須大於 0。")
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
    header = section.header
    header.is_linked_to_previous = False
    paragraph = header.paragraphs[0]
    paragraph.paragraph_format.space_before = 0
    paragraph.paragraph_format.space_after = 0
    paragraph.paragraph_format.line_spacing = 1
    for index, guide in enumerate(guides, start=1):
        run = paragraph.add_run()
        run._r.append(parse_xml(_line_xml(index, guide, stroke_pt)))


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
