"""Cross-platform cover project model and serialization API."""

from .models import (
    CoverElement,
    CoverMetadata,
    CoverProject,
    ElementKind,
    ElementTransform,
    ExportSettings,
    ImageMode,
    Region,
    TrimSize,
)
from .metadata import CoverMetadataInspection, inspect_metadata
from .geometry import CoverLayout, CoverLayoutError, RectMm, calculate_layout
from .print_plan import PrintMark, PrintPage, PrintPlan, build_print_plan
from .project_io import CoverValidationError, dumps_project, loads_project, validate_project
from .templates import TemplateSummary, apply_template, list_templates
from .render import CoverRenderError, RenderResult, mm_to_px, render_preview, render_print_page, render_spread
from .pdf_export import CoverExportError, ExportResult, export_pdf
from .docx_export import export_docx
from .service import export_cover, inspect_source, new_project
from . import service

__all__ = [
    "service",
    "inspect_source",
    "new_project",
    "export_cover",
    "export_docx",
    "export_pdf",
    "ExportResult",
    "CoverExportError",
    "render_spread",
    "render_print_page",
    "render_preview",
    "mm_to_px",
    "RenderResult",
    "CoverRenderError",
    "list_templates",
    "apply_template",
    "TemplateSummary",
    "CoverLayout",
    "CoverLayoutError",
    "PrintMark",
    "PrintPage",
    "PrintPlan",
    "RectMm",
    "build_print_plan",
    "calculate_layout",
    "CoverElement",
    "CoverMetadata",
    "CoverMetadataInspection",
    "CoverProject",
    "CoverValidationError",
    "ElementKind",
    "ElementTransform",
    "ExportSettings",
    "ImageMode",
    "Region",
    "TrimSize",
    "dumps_project",
    "inspect_metadata",
    "loads_project",
    "validate_project",
]
