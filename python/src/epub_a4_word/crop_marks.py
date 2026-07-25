from __future__ import annotations

from dataclasses import dataclass
from docx.oxml import OxmlElement
from docx.oxml import parse_xml

PT_PER_CM = 72.0 / 2.54


@dataclass(frozen=True)
class CropMarkFrame:
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


def _pt(cm: float) -> float:
    return cm * PT_PER_CM


def _line_xml(identifier: int, x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office">'
        f'<v:line id="epub2a4-crop-{identifier}" '
        f'style="position:absolute;z-index:251659264;'
        f'mso-position-horizontal-relative:page;mso-position-vertical-relative:page" '
        f'from="{x1:.3f}pt,{y1:.3f}pt" to="{x2:.3f}pt,{y2:.3f}pt" '
        f'strokecolor="#000000" strokeweight="0.5pt">'
        f'<o:lock v:ext="edit" rotation="t" />'
        f'</v:line></w:pict>'
    )


def add_crop_marks(
    section,
    frame: CropMarkFrame,
    *,
    length_mm: float = 5.0,
    gap_mm: float = 2.0,
) -> None:
    """Add eight print crop-mark segments outside the trim rectangle."""
    if length_mm <= 0 or gap_mm < 0:
        raise ValueError("裁切標記長度與間距無效。")
    length = length_mm / 10.0
    gap = gap_mm / 10.0
    left, right = frame.left_cm, frame.right_cm
    top, bottom = frame.top_cm, frame.bottom_cm
    segments_cm = (
        # top-left horizontal / vertical
        (left - gap - length, top, left - gap, top),
        (left, top - gap - length, left, top - gap),
        # top-right
        (right + gap, top, right + gap + length, top),
        (right, top - gap - length, right, top - gap),
        # bottom-left
        (left - gap - length, bottom, left - gap, bottom),
        (left, bottom + gap, left, bottom + gap + length),
        # bottom-right
        (right + gap, bottom, right + gap + length, bottom),
        (right, bottom + gap, right, bottom + gap + length),
    )
    # All segments must remain on the physical page and outside the trim frame.
    for x1, y1, x2, y2 in segments_cm:
        if min(x1, x2) < 0 or max(x1, x2) > frame.page_width_cm:
            raise ValueError("裁切標記超出紙張水平範圍。")
        if min(y1, y2) < 0 or max(y1, y2) > frame.page_height_cm:
            raise ValueError("裁切標記超出紙張垂直範圍。")

    header = section.header
    header.is_linked_to_previous = False
    paragraph = header.paragraphs[0]
    paragraph.paragraph_format.space_before = 0
    paragraph.paragraph_format.space_after = 0
    paragraph.paragraph_format.line_spacing = 1
    for index, (x1, y1, x2, y2) in enumerate(segments_cm, start=1):
        run = paragraph.add_run()
        run._r.append(
            parse_xml(_line_xml(index, _pt(x1), _pt(y1), _pt(x2), _pt(y2)))
        )
