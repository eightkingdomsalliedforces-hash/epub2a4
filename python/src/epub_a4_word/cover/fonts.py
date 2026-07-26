from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re
import sys
from collections.abc import Iterable

from PIL import ImageFont

_FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc"})
_FILE_ALIASES: dict[str, tuple[str, ...]] = {
    "yuantitc": ("yuanti",),
    "pingfangtc": ("pingfang",),
    "microsoftjhengheiui": ("msjh", "msjhl"),
    "microsoftjhenghei": ("msjh",),
    "notosanscjktc": ("notosanscjk", "notosanstc"),
    "notosanstc": ("notosanstc", "notosanscjk"),
    "sansserif": ("dejavusans", "liberationsans"),
    "monospace": ("dejavusansmono", "liberationmono"),
}


def _normalize_hint(value: object) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(value).casefold())


def _font_directories() -> tuple[Path, ...]:
    values: list[Path] = []
    configured = os.environ.get("EPUB2A4_FONT_DIRS", "")
    if configured:
        values.extend(Path(item).expanduser() for item in configured.split(os.pathsep) if item)
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        values.append(windir / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            values.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        values.extend(
            (
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library" / "Fonts",
            )
        )
    else:
        values.extend(
            (
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
                Path.home() / ".local" / "share" / "fonts",
            )
        )
    result: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        path = value.expanduser()
        if path in seen:
            continue
        seen.add(path)
        if path.is_dir():
            result.append(path)
    return tuple(result)


@lru_cache(maxsize=1)
def _installed_font_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for directory in _font_directories():
        try:
            files.extend(
                path
                for path in directory.rglob("*")
                if path.is_file() and path.suffix.casefold() in _FONT_SUFFIXES
            )
        except OSError:
            continue
    return tuple(sorted(set(files), key=lambda item: str(item).casefold()))


def _family_values(font_family: object, fallback_families: Iterable[object]) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(font_family, str):
        values.append(font_family)
    elif font_family is not None:
        values.append(str(font_family))
    values.extend(str(item) for item in fallback_families)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return tuple(result)


def _matching_font_path(families: tuple[str, ...]) -> Path | None:
    files = _installed_font_files()
    if not files:
        return None
    file_keys = tuple((path, _normalize_hint(path.stem)) for path in files)
    for family in families:
        normalized = _normalize_hint(family)
        if not normalized:
            continue
        hints = (normalized,) + _FILE_ALIASES.get(normalized, ())
        ranked: list[tuple[int, int, str, Path]] = []
        for path, stem in file_keys:
            for hint in hints:
                if stem == hint:
                    rank = 0
                elif stem.startswith(hint) or hint.startswith(stem):
                    rank = 1
                elif hint in stem:
                    rank = 2
                else:
                    continue
                ranked.append((rank, abs(len(stem) - len(hint)), str(path).casefold(), path))
                break
        if ranked:
            return min(ranked)[-1]
    return None


def resolve_font(
    font_family: str,
    font_path: str | None,
    size_px: int,
    fallback_families: Iterable[object] = (),
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Resolve an installed local font without downloading or bundling fonts."""

    normalized_size = max(1, int(size_px))
    explicit_candidates = (font_path, os.environ.get("EPUB2A4_DEFAULT_FONT"))
    for candidate in explicit_candidates:
        if candidate and Path(candidate).is_file():
            try:
                return ImageFont.truetype(str(candidate), normalized_size)
            except OSError:
                continue

    families = _family_values(font_family, fallback_families)
    discovered = _matching_font_path(families)
    if discovered is not None:
        try:
            return ImageFont.truetype(str(discovered), normalized_size)
        except OSError:
            pass

    try:
        return ImageFont.load_default(size=max(8, normalized_size))
    except TypeError:  # Pillow versions before the scalable default font.
        return ImageFont.load_default()
