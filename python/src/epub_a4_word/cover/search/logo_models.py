from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit


class LogoSourceCategory(StrEnum):
    OFFICIAL = "official"
    OFFICIAL_SOCIAL = "official_social"
    WIKIMEDIA = "wikimedia"
    WIKIPEDIA = "wikipedia"
    OTHER = "other"
    MANUAL = "manual"


def _require_web_url(label: str, value: str) -> None:
    if not value:
        return
    if urlsplit(value).scheme.casefold() not in {"http", "https"}:
        raise ValueError(f"{label} 必須使用 HTTP 或 HTTPS。")


def normalized_logo_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path,
            parsed.query,
            "",
        )
    )


@dataclass(frozen=True)
class LogoCandidate:
    provider: str
    candidate_id: str
    title: str
    image_url: str
    preview_url: str
    source_page: str
    source_category: LogoSourceCategory
    source_domain: str = ""
    width_px: int | None = None
    height_px: int | None = None
    media_type: str = ""
    transparent_background: bool | None = None
    license_text: str = ""
    official_source: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_category", LogoSourceCategory(self.source_category))
        for label, value in (
            ("image_url", self.image_url),
            ("preview_url", self.preview_url),
            ("source_page", self.source_page),
        ):
            _require_web_url(label, value)
        if self.width_px is not None and self.width_px <= 0:
            raise ValueError("width_px 必須大於 0。")
        if self.height_px is not None and self.height_px <= 0:
            raise ValueError("height_px 必須大於 0。")

    @property
    def pixel_area(self) -> int:
        return int(self.width_px or 0) * int(self.height_px or 0)

    @property
    def dedupe_key(self) -> str:
        return normalized_logo_url(self.image_url)


@dataclass(frozen=True)
class LogoSearchPage:
    candidates: tuple[LogoCandidate, ...] = ()
    next_page_token: str | None = None
    warnings: tuple[str, ...] = ()
