from __future__ import annotations

from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.shared import Cm, Pt
from lxml import etree

_PT_PER_CM = 72.0 / 2.54
_MM_PER_CM = 10.0
_VML_NS = "urn:schemas-microsoft-com:vml"


@dataclass(frozen=True)
class CropMarkFrame:
    page_width_cm: float
    page_height_cm: float
    left_cm: float
    top_cm: float
    width_cm: float
    height_cm: float

    def __post_init__(self) -> None:
        if self.page_width_cm <= 0 or self.page_height_cm <= 0:
            raise ValueError("裁切標記頁面尺寸必須大於 0。")
        if self.width_cm <= 0 or self.height_cm <= 0:
            raise ValueError("裁切框尺寸必須大於 0。")
        if self.left_cm < 0 or self.top_cm < 0:
            raise ValueError("裁切框座標不可小於 0。")
        if self.right_cm > self.page_width_cm or self.bottom_cm > self.page_height_cm:
            raise ValueError("裁切框不可超出頁面。")

    @property
    def right_cm(self) -> float:
        return self.left_cm + self.width_cm

    @property
    def bottom_cm(self) -> float:
        return self.top_cm + self.height_cm


def _cm_to_pt(value: float) -> float:
    return value * _PT_PER_CM


def _append_vml_line(
    paragraph,
    *,
    x1_pt: float,
    y1_pt: float,
    x2_pt: float,
    y2_pt: float,
) -> None:
    left = min(x1_pt, x2_pt)
    top = min(y1_pt, y2_pt)
    width = abs(x2_pt - x1_pt)
    height = abs(y2_pt - y1_pt)

    if x1_pt == x2_pt:
        from_x = to_x = 0
    elif x2_pt > x1_pt:
        from_x, to_x = 0, 21600
    else:
        from_x, to_x = 21600, 0
    if y1_pt == y2_pt:
        from_y = to_y = 0
    elif y2_pt > y1_pt:
        from_y, to_y = 0, 21600
    else:
        from_y, to_y = 21600, 0

    pict = OxmlElement("w:pict")
    line = etree.Element(f"{{{_VML_NS}}}line", nsmap={"v": _VML_NS})
    line.set("from", f"{from_x},{from_y}")
    line.set("to", f"{to_x},{to_y}")
    line.set("strokecolor", "#000000")
    line.set("strokeweight", "0.5pt")
    line.set(
        "style",
        (
            f"position:absolute;left:{left:.3f}pt;top:{top:.3f}pt;"
            f"width:{width:.3f}pt;height:{height:.3f}pt;"
            "mso-position-horizontal-relative:page;"
            "mso-position-vertical-relative:page;"
            "z-index:251659264"
        ),
    )
    pict.append(line)
    paragraph._p.append(pict)


def add_crop_marks(
    section,
    frame: CropMarkFrame,
    length_mm: float = 5.0,
    gap_mm: float = 2.0,
) -> None:
    if length_mm <= 0:
        raise ValueError("裁切標記長度必須大於 0。")
    if gap_mm < 0:
        raise ValueError("裁切標記間距不可小於 0。")

    length_cm = length_mm / _MM_PER_CM
    gap_cm = gap_mm / _MM_PER_CM
    left = frame.left_cm
    top = frame.top_cm
    right = frame.right_cm
    bottom = frame.bottom_cm

    segments_cm = (
        (left - gap_cm - length_cm, top, left - gap_cm, top),
        (left, top - gap_cm - length_cm, left, top - gap_cm),
        (right + gap_cm, top, right + gap_cm + length_cm, top),
        (right, top - gap_cm - length_cm, right, top - gap_cm),
        (left - gap_cm - length_cm, bottom, left - gap_cm, bottom),
        (left, bottom + gap_cm, left, bottom + gap_cm + length_cm),
        (right + gap_cm, bottom, right + gap_cm + length_cm, bottom),
        (right, bottom + gap_cm, right, bottom + gap_cm + length_cm),
    )
    for x1, y1, x2, y2 in segments_cm:
        if min(x1, x2) < 0 or max(x1, x2) > frame.page_width_cm:
            raise ValueError("水平裁切標記超出頁面。")
        if min(y1, y2) < 0 or max(y1, y2) > frame.page_height_cm:
            raise ValueError("垂直裁切標記超出頁面。")

    section.header_distance = Cm(0)
    paragraph = section.header.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = Pt(1)
    for x1, y1, x2, y2 in segments_cm:
        _append_vml_line(
            paragraph,
            x1_pt=_cm_to_pt(x1),
            y1_pt=_cm_to_pt(y1),
            x2_pt=_cm_to_pt(x2),
            y2_pt=_cm_to_pt(y2),
        )
