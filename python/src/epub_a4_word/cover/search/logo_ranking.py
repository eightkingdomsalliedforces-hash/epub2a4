from __future__ import annotations

import math
import re
from urllib.parse import urlsplit

from ..publisher_directory import PublisherProfile
from .logo_models import LogoCandidate, LogoSourceCategory

_SOURCE_WEIGHT = {
    LogoSourceCategory.OFFICIAL: 1000,
    LogoSourceCategory.OFFICIAL_SOCIAL: 850,
    LogoSourceCategory.WIKIMEDIA: 650,
    LogoSourceCategory.WIKIPEDIA: 550,
    LogoSourceCategory.OTHER: 250,
    LogoSourceCategory.MANUAL: 1200,
}


def _terms(profile: PublisherProfile) -> tuple[str, ...]:
    return tuple(
        re.sub(r"\s+", "", value).casefold()
        for value in (profile.display_name, *profile.aliases)
        if value.strip()
    )


def logo_candidate_score(candidate: LogoCandidate, profile: PublisherProfile) -> float:
    score = float(_SOURCE_WEIGHT[candidate.source_category])
    host = urlsplit(candidate.source_page or candidate.image_url).hostname or ""
    if candidate.official_source or any(
        host == domain or host.endswith("." + domain)
        for domain in profile.official_domains
    ):
        score += 500
    if candidate.transparent_background is True:
        score += 140
    elif candidate.transparent_background is False:
        score -= 20
    media = candidate.media_type.casefold()
    if media in {"image/svg+xml", "image/svg"} or candidate.image_url.casefold().endswith(".svg"):
        score += 120
    elif media == "image/png" or candidate.image_url.casefold().endswith(".png"):
        score += 80
    compact_title = re.sub(r"\s+", "", candidate.title).casefold()
    score += 60 * sum(term in compact_title for term in _terms(profile))
    if candidate.pixel_area:
        score += min(80.0, math.log2(max(candidate.pixel_area, 1)) * 3.0)
    title = candidate.title.casefold()
    if any(word in title for word in ("photo", "photograph", "screenshot", "店面", "活動")):
        score -= 180
    return score


def rank_logo_candidates(
    candidates: tuple[LogoCandidate, ...] | list[LogoCandidate],
    profile: PublisherProfile,
) -> tuple[LogoCandidate, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda item: (-logo_candidate_score(item, profile), item.candidate_id),
        )
    )


def dedupe_logo_candidates(
    candidates: tuple[LogoCandidate, ...] | list[LogoCandidate],
    profile: PublisherProfile,
) -> tuple[LogoCandidate, ...]:
    best: dict[str, LogoCandidate] = {}
    for candidate in candidates:
        current = best.get(candidate.dedupe_key)
        if current is None or logo_candidate_score(candidate, profile) > logo_candidate_score(
            current, profile
        ):
            best[candidate.dedupe_key] = candidate
    return rank_logo_candidates(tuple(best.values()), profile)
