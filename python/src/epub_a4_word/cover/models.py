from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ImageMode(StrEnum):
    FRONT_ONLY = "front_only"
    SEPARATE_COVERS = "separate_covers"
    FULL_SPREAD = "full_spread"


class ElementKind(StrEnum):
    IMAGE = "image"
    TEXT = "text"
    SHAPE = "shape"
    BARCODE_PLACEHOLDER = "barcode_placeholder"
    GUIDE = "guide"


class Region(StrEnum):
    BACK = "back"
    SPINE = "spine"
    FRONT = "front"
    SPREAD = "spread"


@dataclass(frozen=True)
class TrimSize:
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class CoverMetadata:
    title: str = ""
    author: str = ""
    description: str = ""
    isbn: str = ""
    publisher: str = ""
    price: str = ""
    publication_place: str = ""
    translator: str = ""
    isbn_addon: str = ""
    language: str = ""
    page_count_is_estimate: bool = False
    embedded_images: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ElementTransform:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    rotation_deg: float = 0.0


@dataclass(frozen=True)
class CoverElement:
    id: str
    kind: ElementKind
    region: Region
    transform: ElementTransform
    z_index: int = 0
    opacity: float = 1.0
    content: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportSettings:
    dpi: int = 300
    show_crop_marks: bool = True
    show_assembly_marks: bool = True


@dataclass(frozen=True)
class CoverProject:
    schema_version: int
    source_file: str
    source_type: str
    metadata: CoverMetadata
    trim_size: TrimSize
    page_count: int
    paper_caliper_mm: float
    manual_spine_width_mm: float | None
    bleed_mm: float
    overlap_mm: float
    image_mode: ImageMode
    working_dir: str = ""
    background: dict[str, Any] = field(default_factory=dict)
    elements: tuple[CoverElement, ...] = ()
    export_settings: ExportSettings = field(default_factory=ExportSettings)

    @property
    def elements_by_id(self) -> dict[str, CoverElement]:
        return {element.id: element for element in self.elements}
