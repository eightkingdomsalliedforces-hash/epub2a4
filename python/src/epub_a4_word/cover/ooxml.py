from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree

from .geometry import RectMm
from .models import CoverElement


EMU_PER_MM = 36000
TWIPS_PER_MM = 1440 / 25.4
POINTS_PER_MM = 72.0 / 25.4
VML_NS = "urn:schemas-microsoft-com:vml"


@dataclass(frozen=True)
class CropPercent:
    """OOXML image crop percentages in 1/1000 percent units (0..100000)."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    def __post_init__(self) -> None:
        for value in (self.left, self.top, self.right, self.bottom):
            if not 0 <= int(value) <= 100000:
                raise ValueError("圖片裁切百分比必須介於 0 與 100000。")
        if self.left + self.right >= 100000 or self.top + self.bottom >= 100000:
            raise ValueError("圖片裁切後必須保留可見區域。")


def mm_to_emu(mm: float) -> int:
    if not math.isfinite(float(mm)):
        raise ValueError("毫米值必須是有限數字。")
    return round(float(mm) * EMU_PER_MM)


def mm_to_twips(mm: float) -> int:
    if not math.isfinite(float(mm)):
        raise ValueError("毫米值必須是有限數字。")
    return round(float(mm) * TWIPS_PER_MM)


def mm_to_points(mm: float) -> float:
    if not math.isfinite(float(mm)):
        raise ValueError("毫米值必須是有限數字。")
    return float(mm) * POINTS_PER_MM


def _set(element: Any, name: str, value: object) -> None:
    element.set(qn(name), str(value))


def _append_text(parent: Any, tag: str, text: object) -> Any:
    element = OxmlElement(tag)
    element.text = str(text)
    parent.append(element)
    return element


def make_anchor(
    *,
    relationship_id: str,
    drawing_id: int,
    x_emu: int,
    y_emu: int,
    width_emu: int,
    height_emu: int,
    crop_left: int = 0,
    crop_top: int = 0,
    crop_right: int = 0,
    crop_bottom: int = 0,
    behind_text: bool = False,
    name: str | None = None,
) -> Any:
    drawing = OxmlElement("w:drawing")
    anchor = OxmlElement("wp:anchor")
    for attr, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": str(max(0, drawing_id)),
        "behindDoc": "1" if behind_text else "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(attr, value)
    drawing.append(anchor)

    simple_pos = OxmlElement("wp:simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    anchor.append(simple_pos)

    position_h = OxmlElement("wp:positionH")
    position_h.set("relativeFrom", "page")
    _append_text(position_h, "wp:posOffset", x_emu)
    anchor.append(position_h)

    position_v = OxmlElement("wp:positionV")
    position_v.set("relativeFrom", "page")
    _append_text(position_v, "wp:posOffset", y_emu)
    anchor.append(position_v)

    extent = OxmlElement("wp:extent")
    extent.set("cx", str(width_emu))
    extent.set("cy", str(height_emu))
    anchor.append(extent)

    effect = OxmlElement("wp:effectExtent")
    for side in ("l", "t", "r", "b"):
        effect.set(side, "0")
    anchor.append(effect)
    anchor.append(OxmlElement("wp:wrapNone"))

    doc_pr = OxmlElement("wp:docPr")
    doc_pr.set("id", str(drawing_id))
    doc_pr.set("name", name or f"Cover picture {drawing_id}")
    anchor.append(doc_pr)

    frame_pr = OxmlElement("wp:cNvGraphicFramePr")
    locks = OxmlElement("a:graphicFrameLocks")
    locks.set("noChangeAspect", "1")
    frame_pr.append(locks)
    anchor.append(frame_pr)

    graphic = OxmlElement("a:graphic")
    graphic_data = OxmlElement("a:graphicData")
    graphic_data.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/picture")
    graphic.append(graphic_data)
    anchor.append(graphic)

    picture = OxmlElement("pic:pic")
    graphic_data.append(picture)

    nv_pic = OxmlElement("pic:nvPicPr")
    c_nv_pr = OxmlElement("pic:cNvPr")
    c_nv_pr.set("id", str(drawing_id))
    c_nv_pr.set("name", name or f"Cover picture {drawing_id}")
    nv_pic.append(c_nv_pr)
    nv_pic.append(OxmlElement("pic:cNvPicPr"))
    picture.append(nv_pic)

    blip_fill = OxmlElement("pic:blipFill")
    blip = OxmlElement("a:blip")
    blip.set(qn("r:embed"), relationship_id)
    blip_fill.append(blip)
    src_rect = OxmlElement("a:srcRect")
    for attr, value in {
        "l": crop_left,
        "t": crop_top,
        "r": crop_right,
        "b": crop_bottom,
    }.items():
        src_rect.set(attr, str(int(value)))
    blip_fill.append(src_rect)
    stretch = OxmlElement("a:stretch")
    stretch.append(OxmlElement("a:fillRect"))
    blip_fill.append(stretch)
    picture.append(blip_fill)

    shape_properties = OxmlElement("pic:spPr")
    transform = OxmlElement("a:xfrm")
    offset = OxmlElement("a:off")
    offset.set("x", "0")
    offset.set("y", "0")
    transform.append(offset)
    ext = OxmlElement("a:ext")
    ext.set("cx", str(width_emu))
    ext.set("cy", str(height_emu))
    transform.append(ext)
    shape_properties.append(transform)
    geometry = OxmlElement("a:prstGeom")
    geometry.set("prst", "rect")
    geometry.append(OxmlElement("a:avLst"))
    shape_properties.append(geometry)
    picture.append(shape_properties)
    return drawing


def add_anchored_picture(
    paragraph: Paragraph,
    image_path: Path,
    rect: RectMm,
    crop: CropPercent,
    drawing_id: int,
    *,
    behind_text: bool = False,
    name: str | None = None,
) -> None:
    relationship_id, _image = paragraph.part.get_or_add_image(str(image_path))
    drawing = make_anchor(
        relationship_id=relationship_id,
        drawing_id=drawing_id,
        x_emu=mm_to_emu(rect.x_mm),
        y_emu=mm_to_emu(rect.y_mm),
        width_emu=mm_to_emu(rect.width_mm),
        height_emu=mm_to_emu(rect.height_mm),
        crop_left=crop.left,
        crop_top=crop.top,
        crop_right=crop.right,
        crop_bottom=crop.bottom,
        behind_text=behind_text,
        name=name,
    )
    paragraph.add_run()._r.append(drawing)


def _hex_color(value: object, default: str = "000000") -> str:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        return default
    return text.upper()


def _shape_style(rect: RectMm, rotation_deg: float, *, z_index: int) -> str:
    return ";".join(
        (
            "position:absolute",
            "margin-left:0",
            "margin-top:0",
            f"left:{mm_to_points(rect.x_mm):.6f}pt",
            f"top:{mm_to_points(rect.y_mm):.6f}pt",
            f"width:{mm_to_points(rect.width_mm):.6f}pt",
            f"height:{mm_to_points(rect.height_mm):.6f}pt",
            f"rotation:{float(rotation_deg):.6f}",
            f"z-index:{int(z_index)}",
            "mso-position-horizontal-relative:page",
            "mso-position-vertical-relative:page",
        )
    )


def make_text_box_shape(
    *,
    shape_id: str,
    rect: RectMm,
    rotation_deg: float,
    text: str,
    font_family: str,
    font_size_pt: float,
    color: str,
    align: str,
    line_spacing: float,
    fill: str | None = None,
    stroke: str | None = None,
    behind_text: bool = False,
    z_index: int = 10,
) -> Any:
    run = OxmlElement("w:r")
    pict = OxmlElement("w:pict")
    run.append(pict)
    shape = etree.Element(f"{{{VML_NS}}}shape", nsmap={"v": VML_NS})
    shape.set("id", shape_id)
    shape.set("type", "#_x0000_t202")
    shape.set("style", _shape_style(rect, rotation_deg, z_index=-1 if behind_text else z_index))
    shape.set("filled", "t" if fill else "f")
    shape.set("fillcolor", f"#{_hex_color(fill, 'FFFFFF')}" if fill else "none")
    shape.set("stroked", "t" if stroke else "f")
    if stroke:
        shape.set("strokecolor", f"#{_hex_color(stroke)}")
    pict.append(shape)

    textbox = etree.Element(f"{{{VML_NS}}}textbox")
    textbox.set("inset", "0,0,0,0")
    shape.append(textbox)
    content = OxmlElement("w:txbxContent")
    textbox.append(content)
    paragraph = OxmlElement("w:p")
    content.append(paragraph)

    paragraph_properties = OxmlElement("w:pPr")
    paragraph.append(paragraph_properties)
    justification = OxmlElement("w:jc")
    _set(justification, "w:val", {"left": "left", "right": "right", "center": "center"}.get(align, "left"))
    paragraph_properties.append(justification)
    spacing = OxmlElement("w:spacing")
    _set(spacing, "w:line", max(1, round(float(line_spacing) * 240)))
    _set(spacing, "w:lineRule", "auto")
    _set(spacing, "w:before", "0")
    _set(spacing, "w:after", "0")
    paragraph_properties.append(spacing)

    text_run = OxmlElement("w:r")
    paragraph.append(text_run)
    run_properties = OxmlElement("w:rPr")
    text_run.append(run_properties)
    fonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        _set(fonts, attr, font_family)
    run_properties.append(fonts)
    size = OxmlElement("w:sz")
    _set(size, "w:val", max(1, round(float(font_size_pt) * 2)))
    run_properties.append(size)
    size_cs = OxmlElement("w:szCs")
    _set(size_cs, "w:val", max(1, round(float(font_size_pt) * 2)))
    run_properties.append(size_cs)
    color_node = OxmlElement("w:color")
    _set(color_node, "w:val", _hex_color(color))
    run_properties.append(color_node)
    text_node = OxmlElement("w:t")
    text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = text
    text_run.append(text_node)
    return run


def add_text_box(paragraph: Paragraph, element: CoverElement, rect: RectMm) -> None:
    content = element.content
    shape = make_text_box_shape(
        shape_id=f"textbox-{element.id}",
        rect=rect,
        rotation_deg=element.transform.rotation_deg,
        text=str(content.get("text", "")),
        font_family=str(content.get("font_family", "sans-serif")),
        font_size_pt=float(content.get("font_size_pt", 10.0)),
        color=str(content.get("color", "#000000")),
        align=str(content.get("align", "left")),
        line_spacing=float(content.get("line_spacing", 1.0)),
        fill=content.get("fill"),
        stroke=content.get("stroke"),
        z_index=element.z_index,
    )
    paragraph._p.append(shape)


def make_line_shape(
    *,
    shape_id: str,
    x1_pt: float,
    y1_pt: float,
    x2_pt: float,
    y2_pt: float,
    behind_text: bool = True,
    dash_style: str = "solid",
) -> Any:
    run = OxmlElement("w:r")
    pict = OxmlElement("w:pict")
    run.append(pict)
    line = etree.Element(f"{{{VML_NS}}}line", nsmap={"v": VML_NS})
    line.set("id", shape_id)
    line.set("from", f"{x1_pt:.6f}pt,{y1_pt:.6f}pt")
    line.set("to", f"{x2_pt:.6f}pt,{y2_pt:.6f}pt")
    line.set(
        "style",
        ";".join(
            (
                "position:absolute",
                "margin-left:0",
                "margin-top:0",
                f"z-index:{-1 if behind_text else 1}",
                "mso-position-horizontal-relative:page",
                "mso-position-vertical-relative:page",
            )
        ),
    )
    line.set("strokecolor", "#000000")
    line.set("strokeweight", "0.5pt")
    if dash_style == "dashed":
        line.set("dashstyle", "dash")
    elif dash_style == "dotted":
        line.set("dashstyle", "dot")
    pict.append(line)
    return run


def add_line_shape(
    paragraph: Paragraph,
    *,
    shape_id: str,
    x1_mm: float,
    y1_mm: float,
    x2_mm: float,
    y2_mm: float,
    behind_text: bool = True,
    dash_style: str = "solid",
) -> None:
    paragraph._p.append(
        make_line_shape(
            shape_id=shape_id,
            x1_pt=mm_to_points(x1_mm),
            y1_pt=mm_to_points(y1_mm),
            x2_pt=mm_to_points(x2_mm),
            y2_pt=mm_to_points(y2_mm),
            behind_text=behind_text,
            dash_style=dash_style,
        )
    )
