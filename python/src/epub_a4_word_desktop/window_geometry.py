from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowGeometry:
    x: int
    y: int
    width: int
    height: int


def fit_initial_window(
    *,
    available_x: int,
    available_y: int,
    available_width: int,
    available_height: int,
    target_width: int = 1280,
    target_height: int = 820,
) -> WindowGeometry:
    """Return a centered startup rectangle that never exceeds usable screen space."""
    width_limit = max(1, int(available_width))
    height_limit = max(1, int(available_height))
    width = min(int(target_width), max(1, int(width_limit * 0.96)), width_limit)
    height = min(int(target_height), max(1, int(height_limit * 0.96)), height_limit)
    x = int(available_x) + max(0, (width_limit - width) // 2)
    y = int(available_y) + max(0, (height_limit - height) // 2)
    return WindowGeometry(x=x, y=y, width=width, height=height)