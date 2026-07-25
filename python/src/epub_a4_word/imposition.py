from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ImpositionMode = Literal[
    "four_up",
    "signature16",
    "single_a5",
    "single_4x6",
    "b6_on_a5",
]
PageSlot = int | None
SideSlots = tuple[PageSlot, ...]


@dataclass(frozen=True)
class ImpositionPlan:
    """A sequence of physical print sides in row-major cell order."""

    mode: ImpositionMode
    sides: tuple[SideSlots, ...]
    paper_sheet_count: int
    signature_count: int
    padded_page_count: int


def _visible_page(page_number: int, page_count: int) -> PageSlot:
    return page_number if page_number <= page_count else None


def _build_four_up(page_count: int) -> ImpositionPlan:
    padded = max(4, ((page_count + 3) // 4) * 4)
    sides: list[SideSlots] = []
    for start in range(1, padded + 1, 4):
        sides.append(tuple(_visible_page(start + offset, page_count) for offset in range(4)))
    return ImpositionPlan(
        mode="four_up",
        sides=tuple(sides),
        paper_sheet_count=len(sides),
        signature_count=0,
        padded_page_count=padded,
    )


def _build_signature16(page_count: int) -> ImpositionPlan:
    signature_count = max(1, (page_count + 15) // 16)
    padded = signature_count * 16
    sides: list[SideSlots] = []
    relative_sides = (
        (16, 1, 14, 3),
        (2, 15, 4, 13),
        (12, 5, 10, 7),
        (6, 11, 8, 9),
    )
    for signature_index in range(signature_count):
        base = signature_index * 16
        for relative in relative_sides:
            sides.append(tuple(_visible_page(base + page, page_count) for page in relative))
    return ImpositionPlan(
        mode="signature16",
        sides=tuple(sides),
        paper_sheet_count=signature_count * 2,
        signature_count=signature_count,
        padded_page_count=padded,
    )


def _build_single_page(page_count: int, mode: ImpositionMode) -> ImpositionPlan:
    sides: tuple[SideSlots, ...] = tuple(
        (page_number,) for page_number in range(1, page_count + 1)
    )
    return ImpositionPlan(
        mode=mode,
        sides=sides,
        paper_sheet_count=len(sides),
        signature_count=0,
        padded_page_count=page_count,
    )


def build_imposition(page_count: int, mode: ImpositionMode = "four_up") -> ImpositionPlan:
    if page_count < 0:
        raise ValueError("page_count must not be negative")
    if mode == "four_up":
        return _build_four_up(page_count)
    if mode == "signature16":
        return _build_signature16(page_count)
    if mode in {"single_a5", "single_4x6", "b6_on_a5"}:
        return _build_single_page(page_count, mode)
    raise ValueError(f"Unsupported imposition mode: {mode}")
