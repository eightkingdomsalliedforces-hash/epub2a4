from __future__ import annotations

from dataclasses import dataclass

from .isbn import (
    canonical_isbn13,
    encode_ean13_modules,
    encode_ean_addon_modules,
    normalize_ean_addon,
)


@dataclass(frozen=True)
class BarcodeBar:
    x: float
    width: float
    top: float
    bottom: float


@dataclass(frozen=True)
class BarcodeTextAnchor:
    text: str
    left: float
    top: float
    right: float
    bottom: float
    align: str = "center"


@dataclass(frozen=True)
class BarcodeLayout:
    data_bars: tuple[BarcodeBar, ...]
    guard_bars: tuple[BarcodeBar, ...]
    addon_bars: tuple[BarcodeBar, ...]
    first_digit: BarcodeTextAnchor
    left_digits: BarcodeTextAnchor
    right_digits: BarcodeTextAnchor
    addon_digits: BarcodeTextAnchor | None

    @property
    def bars(self) -> tuple[BarcodeBar, ...]:
        return self.data_bars + self.guard_bars + self.addon_bars


_EAN_GUARD_INDICES = frozenset({0, 2, 46, 48, 92, 94})


def build_barcode_layout(isbn: object, addon: object = "") -> BarcodeLayout:
    """Build normalized EAN-13 and add-on geometry shared by Qt and Pillow."""

    normalized_isbn = canonical_isbn13(isbn)
    if not normalized_isbn:
        raise ValueError("條碼必須使用有效的 ISBN-10 或 ISBN-13。")
    normalized_addon = normalize_ean_addon(addon)
    main_modules = encode_ean13_modules(normalized_isbn)
    addon_modules = encode_ean_addon_modules(normalized_addon)

    quiet_left = 9
    quiet_right = 7
    addon_gap = 8 if addon_modules else 0
    total_modules = quiet_left + len(main_modules) + quiet_right + addon_gap + len(addon_modules)
    module_width = 1.0 / max(1, total_modules)
    main_left = quiet_left * module_width

    data_bars: list[BarcodeBar] = []
    guard_bars: list[BarcodeBar] = []
    for index, bit in enumerate(main_modules):
        if bit != "1":
            continue
        bar = BarcodeBar(
            x=main_left + index * module_width,
            width=module_width,
            top=0.0,
            bottom=0.82 if index in _EAN_GUARD_INDICES else 0.72,
        )
        if index in _EAN_GUARD_INDICES:
            guard_bars.append(bar)
        else:
            data_bars.append(bar)

    addon_bars: list[BarcodeBar] = []
    addon_left = (quiet_left + len(main_modules) + quiet_right + addon_gap) * module_width
    for index, bit in enumerate(addon_modules):
        if bit == "1":
            addon_bars.append(
                BarcodeBar(
                    x=addon_left + index * module_width,
                    width=module_width,
                    top=0.19,
                    bottom=0.72,
                )
            )

    digits_top = 0.78
    first_digit = BarcodeTextAnchor(
        normalized_isbn[0],
        0.0,
        digits_top,
        max(0.0, main_left - module_width * 0.4),
        1.0,
        "right",
    )
    left_digits = BarcodeTextAnchor(
        normalized_isbn[1:7],
        main_left + 3 * module_width,
        digits_top,
        main_left + 45 * module_width,
        1.0,
    )
    right_digits = BarcodeTextAnchor(
        normalized_isbn[7:13],
        main_left + 50 * module_width,
        digits_top,
        main_left + 92 * module_width,
        1.0,
    )
    addon_digits = (
        BarcodeTextAnchor(
            normalized_addon,
            addon_left,
            0.0,
            addon_left + len(addon_modules) * module_width,
            0.16,
        )
        if addon_modules
        else None
    )
    return BarcodeLayout(
        data_bars=tuple(data_bars),
        guard_bars=tuple(guard_bars),
        addon_bars=tuple(addon_bars),
        first_digit=first_digit,
        left_digits=left_digits,
        right_digits=right_digits,
        addon_digits=addon_digits,
    )
