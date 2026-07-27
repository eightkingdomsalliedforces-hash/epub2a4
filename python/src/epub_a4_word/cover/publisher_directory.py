from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class PublisherProfile:
    publisher_id: str
    display_name: str
    aliases: tuple[str, ...] = ()
    official_domains: tuple[str, ...] = ()
    official_urls: tuple[str, ...] = ()
    official_social_urls: tuple[str, ...] = ()
    logo_search_terms: tuple[str, ...] = ()


def _key(value: str) -> str:
    return re.sub(r"[\s\-_.・]+", "", value).casefold()


_PROFILES = (
    PublisherProfile(
        publisher_id="taiwan-kadokawa",
        display_name="台灣角川",
        aliases=("角川", "Kadokawa Taiwan", "KADOKAWA TAIWAN"),
        official_domains=("kadokawa.com.tw",),
        official_urls=("https://www.kadokawa.com.tw/",),
        logo_search_terms=("台灣角川 logo", "KADOKAWA TAIWAN logo"),
    ),
    PublisherProfile(
        publisher_id="sharp-point",
        display_name="尖端出版",
        aliases=("尖端", "Sharp Point Press"),
        official_domains=("spp.com.tw", "espp.com.tw"),
        official_urls=("https://www.espp.com.tw/",),
        logo_search_terms=("尖端出版 logo",),
    ),
    PublisherProfile(
        publisher_id="tong-li",
        display_name="東立出版社",
        aliases=("東立", "Tong Li"),
        official_domains=("tongli.com.tw",),
        official_urls=("https://www.tongli.com.tw/",),
        logo_search_terms=("東立出版社 logo", "Tong Li logo"),
    ),
    PublisherProfile(
        publisher_id="ching-win",
        display_name="青文出版社",
        aliases=("青文", "Ching Win"),
        official_domains=("ching-win.com.tw",),
        official_urls=("https://www.ching-win.com.tw/",),
        logo_search_terms=("青文出版社 logo", "Ching Win logo"),
    ),
)

_INDEX: dict[str, PublisherProfile] = {}
for _profile in _PROFILES:
    for _name in (_profile.display_name, _profile.publisher_id, *_profile.aliases):
        _INDEX[_key(_name)] = _profile


def publisher_profiles() -> tuple[PublisherProfile, ...]:
    return _PROFILES


def publisher_profile(value: str) -> PublisherProfile:
    text = str(value).strip()
    existing = _INDEX.get(_key(text))
    if existing is not None:
        return existing
    slug = re.sub(r"[^0-9A-Za-z]+", "-", text).strip("-").casefold()
    if not slug:
        slug = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return PublisherProfile(
        publisher_id=f"custom-{slug}",
        display_name=text,
        logo_search_terms=(f"{text} logo",) if text else (),
    )
