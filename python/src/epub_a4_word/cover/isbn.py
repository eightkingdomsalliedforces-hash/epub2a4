from __future__ import annotations

from collections.abc import Iterable
import re

_L_PATTERNS = (
    "0001101",
    "0011001",
    "0010011",
    "0111101",
    "0100011",
    "0110001",
    "0101111",
    "0111011",
    "0110111",
    "0001011",
)
_G_PATTERNS = tuple("".join("1" if bit == "0" else "0" for bit in pattern[::-1]) for pattern in _L_PATTERNS)
_R_PATTERNS = tuple("".join("1" if bit == "0" else "0" for bit in pattern) for pattern in _L_PATTERNS)
_EAN13_PARITY = (
    "LLLLLL",
    "LLGLGG",
    "LLGGLG",
    "LLGGGL",
    "LGLLGG",
    "LGGLLG",
    "LGGGLL",
    "LGLGLG",
    "LGLGGL",
    "LGGLGL",
)
_EAN2_PARITY = ("LL", "LG", "GL", "GG")
_EAN5_PARITY = (
    "GGLLL",
    "GLGLL",
    "GLLGL",
    "GLLLG",
    "LGGLL",
    "LLGGL",
    "LLLGG",
    "LGLGL",
    "LGLLG",
    "LLGLG",
)


def normalize_isbn(value: object) -> str:
    """Return a compact checksum-valid ISBN-10/13, otherwise an empty string."""

    text = re.sub(r"^urn:isbn:", "", str(value or "").strip(), flags=re.IGNORECASE)
    compact = re.sub(r"[\s-]", "", text).upper()
    if re.fullmatch(r"\d{9}[\dX]", compact):
        total = sum((10 - index) * (10 if digit == "X" else int(digit)) for index, digit in enumerate(compact))
        return compact if total % 11 == 0 else ""
    if re.fullmatch(r"97[89]\d{10}", compact):
        total = sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(compact[:12]))
        check = (10 - total % 10) % 10
        return compact if check == int(compact[-1]) else ""
    return ""


def isbn13_from_isbn10(value: object) -> str:
    """Convert a checksum-valid ISBN-10 to its 978-prefixed ISBN-13 form."""

    isbn10 = normalize_isbn(value)
    if len(isbn10) != 10:
        return ""
    body = "978" + isbn10[:9]
    total = sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(body))
    return body + str((10 - total % 10) % 10)


def canonical_isbn13(value: object) -> str:
    """Return a valid ISBN as EAN-13, converting ISBN-10 when necessary."""

    isbn = normalize_isbn(value)
    if len(isbn) == 13:
        return isbn
    if len(isbn) == 10:
        return isbn13_from_isbn10(isbn)
    return ""


def valid_isbns(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_isbn(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


def preferred_isbn(values: Iterable[object]) -> str:
    normalized = valid_isbns(values)
    direct = next((value for value in normalized if len(value) == 13), "")
    if direct:
        return direct
    return isbn13_from_isbn10(normalized[0]) if normalized else ""


def normalize_ean_addon(value: object) -> str:
    compact = re.sub(r"\D", "", str(value or ""))
    return compact if len(compact) in {2, 5} else ""


def encode_ean13_modules(value: object) -> str:
    isbn = canonical_isbn13(value)
    if len(isbn) != 13:
        raise ValueError("EAN-13 條碼需要有效的 ISBN-13。")
    first = int(isbn[0])
    left_digits = isbn[1:7]
    right_digits = isbn[7:]
    left = "".join(
        (_L_PATTERNS if parity == "L" else _G_PATTERNS)[int(digit)]
        for digit, parity in zip(left_digits, _EAN13_PARITY[first], strict=True)
    )
    right = "".join(_R_PATTERNS[int(digit)] for digit in right_digits)
    return "101" + left + "01010" + right + "101"


def encode_ean_addon_modules(value: object) -> str:
    addon = normalize_ean_addon(value)
    if not addon:
        return ""
    if len(addon) == 2:
        parity = _EAN2_PARITY[int(addon) % 4]
    else:
        digits = tuple(int(digit) for digit in addon)
        checksum = (sum(digits[::2]) * 3 + sum(digits[1::2]) * 9) % 10
        parity = _EAN5_PARITY[checksum]
    encoded = []
    for index, (digit, mode) in enumerate(zip(addon, parity, strict=True)):
        if index:
            encoded.append("01")
        encoded.append((_L_PATTERNS if mode == "L" else _G_PATTERNS)[int(digit)])
    return "1011" + "".join(encoded)
