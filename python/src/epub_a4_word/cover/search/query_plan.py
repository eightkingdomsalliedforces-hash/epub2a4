from __future__ import annotations

from collections.abc import Iterable
import re
import unicodedata

from .models import BookIdentity, QueryItem, QueryPlan, ResolvedAlias

_EDITION_LABELS = (
    "繁體中文版",
    "简体中文版",
    "簡體中文版",
    "繁体中文版",
    "中文版",
    "電子書版",
    "电子书版",
    "電子版",
    "完整版",
)
_FILE_SUFFIX_RE = re.compile(r"\.(?:epub|mobi|azw3?|pdf|txt)$", re.IGNORECASE)
_SITE_SUFFIX_RE = re.compile(
    r"\s*[\[(（](?:[^\])）]*(?:z-?library|1lib|z-lib)[^\])）]*)[\])）]\s*$",
    re.IGNORECASE,
)
_EDITION_GROUP_RE = re.compile(
    r"\s*[\[(（]\s*(?:" + "|".join(map(re.escape, _EDITION_LABELS)) + r")\s*[\])）]",
    re.IGNORECASE,
)
_EDITION_WORD_RE = re.compile(
    r"(?:^|\s)(?:" + "|".join(map(re.escape, _EDITION_LABELS)) + r")(?:$|\s)",
    re.IGNORECASE,
)
_VOLUME_PATTERNS = (
    re.compile(r"(?:^|\s)第\s*(?P<volume>\d{1,3}|[IVXLCDM]+)\s*[卷冊册集]\s*$", re.IGNORECASE),
    re.compile(
        r"(?:^|\s)(?:vol(?:ume)?|book)\.?\s*(?P<volume>\d{1,3}|[IVXLCDM]+)\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"(?:\s+|[-_])(?P<volume>\d{1,3}|[IVXLCDM]+)\s*$", re.IGNORECASE),
)
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _collapse(value: str) -> str:
    return " ".join(value.split())


def _normalized_key(value: str) -> str:
    return _collapse(unicodedata.normalize("NFKC", value)).casefold()


def _roman_to_int(value: str) -> int | None:
    text = value.upper()
    if not text or any(char not in _ROMAN_VALUES for char in text):
        return None
    total = 0
    previous = 0
    for char in reversed(text):
        current = _ROMAN_VALUES[char]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    # Reject non-canonical strings such as IIX.
    if total <= 0 or _int_to_roman(total) != text:
        return None
    return total


def _int_to_roman(value: int) -> str:
    pairs = (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    )
    remaining = value
    result: list[str] = []
    for amount, numeral in pairs:
        while remaining >= amount:
            result.append(numeral)
            remaining -= amount
    return "".join(result)


def _volume_number(value: str) -> str:
    if value.isdigit():
        return str(int(value))
    roman = _roman_to_int(value)
    return str(roman) if roman is not None else ""


def _split_volume(title: str) -> tuple[str, str]:
    for pattern in _VOLUME_PATTERNS:
        match = pattern.search(title)
        if match is None:
            continue
        volume = _volume_number(match.group("volume"))
        if not volume:
            continue
        base = title[: match.start()].rstrip(" -_：:")
        if base:
            return base, volume
    return title, ""


def normalize_isbn(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"^\s*urn:isbn:\s*", "", text, flags=re.IGNORECASE)
    candidate = re.sub(r"[^0-9Xx]", "", text).upper()
    if len(candidate) == 10 and _valid_isbn10(candidate):
        return candidate
    if len(candidate) == 13 and _valid_isbn13(candidate):
        return candidate
    return ""


def _valid_isbn10(value: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", value):
        return False
    total = sum((10 - index) * (10 if char == "X" else int(char)) for index, char in enumerate(value))
    return total % 11 == 0


def _valid_isbn13(value: str) -> bool:
    if not value.isdigit():
        return False
    total = sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(value[:12]))
    check = (10 - total % 10) % 10
    return check == int(value[-1])


def normalize_book_identity(
    *,
    title: str,
    author: str = "",
    isbn: str = "",
    language: str = "",
) -> BookIdentity:
    original_title = str(title or "").strip()
    working = unicodedata.normalize("NFKC", original_title)
    working = _FILE_SUFFIX_RE.sub("", working.strip())
    working = _SITE_SUFFIX_RE.sub("", working)
    working = _EDITION_GROUP_RE.sub(" ", working)
    working = _EDITION_WORD_RE.sub(" ", working)
    working = _collapse(working).strip(" -_：:")
    normalized_title, volume = _split_volume(working)
    normalized_title = _collapse(normalized_title).strip(" -_：:")

    clean_author = _collapse(unicodedata.normalize("NFKC", str(author or "")).strip())
    return BookIdentity(
        original_title=original_title,
        normalized_title=normalized_title or working or original_title,
        author=clean_author,
        normalized_author=clean_author.casefold() if clean_author.isascii() else clean_author,
        volume=volume,
        isbn=normalize_isbn(str(isbn or "")),
        language=str(language or "").strip(),
    )


def build_query_plan(
    identity: BookIdentity,
    *,
    manual_alias: str = "",
    aliases: Iterable[ResolvedAlias] = (),
    isbns: Iterable[str] = (),
    accepted_aliases: Iterable[ResolvedAlias] = (),
) -> QueryPlan:
    items: list[QueryItem] = []
    seen: set[tuple[str, str]] = set()

    def append(
        *,
        kind: str,
        value: str,
        language: str,
        confidence: str,
        source: str,
        reason: str,
    ) -> None:
        clean = _collapse(str(value or "").strip())
        if not clean:
            return
        normalized = normalize_isbn(clean) if kind == "isbn" else _normalized_key(clean)
        if not normalized:
            return
        key = (kind, normalized)
        if key in seen:
            return
        seen.add(key)
        items.append(
            QueryItem(
                kind=kind,
                value=normalized if kind == "isbn" else clean,
                author=identity.author,
                language=language,
                confidence=confidence,
                source=source,
                reason=reason,
            )
        )

    if identity.isbn:
        append(
            kind="isbn", value=identity.isbn, language=identity.language,
            confidence="high", source="epub", reason="EPUB metadata ISBN",
        )
    for value in isbns:
        append(
            kind="isbn", value=value, language=identity.language,
            confidence="high", source="resolved", reason="resolved ISBN",
        )
    append(
        kind="title", value=manual_alias, language="", confidence="high",
        source="user", reason="user-provided formal title alias",
    )
    for alias in accepted_aliases:
        append(
            kind="title",
            value=alias.value,
            language=alias.language or "",
            confidence="high",
            source=alias.source,
            reason="user-confirmed alias",
        )
    append(
        kind="title", value=identity.original_title, language=identity.language,
        confidence="high", source="epub", reason="original EPUB title",
    )
    append(
        kind="title", value=identity.normalized_title, language=identity.language,
        confidence="high", source="normalized", reason="normalized EPUB title",
    )
    for alias in aliases:
        if alias.confidence.casefold() != "high":
            continue
        append(
            kind="title",
            value=alias.value,
            language=alias.language or "",
            confidence=alias.confidence,
            source=alias.source,
            reason="; ".join(alias.reasons) or "resolved title alias",
        )
    return QueryPlan(identity=identity, items=tuple(items))
