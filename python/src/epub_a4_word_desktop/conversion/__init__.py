"""Desktop conversion adapters and controllers."""

from __future__ import annotations

from .legacy_adapter import (
    ConversionCancelled,
    LegacyConversionRequest,
    allowed_modes_for_path,
    run_conversion,
)

__all__ = [
    "ConversionCancelled",
    "LegacyConversionRequest",
    "allowed_modes_for_path",
    "run_conversion",
]
