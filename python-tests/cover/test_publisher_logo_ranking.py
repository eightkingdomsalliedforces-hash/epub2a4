from __future__ import annotations

from epub_a4_word.cover.publisher_directory import publisher_profile
from epub_a4_word.cover.search.logo_models import LogoCandidate, LogoSourceCategory
from epub_a4_word.cover.search.logo_ranking import dedupe_logo_candidates, rank_logo_candidates


def _candidate(
    candidate_id: str,
    *,
    source: LogoSourceCategory,
    url: str | None = None,
    transparent: bool | None = None,
    media_type: str = "image/png",
    width: int = 500,
    height: int = 200,
    official: bool = False,
) -> LogoCandidate:
    return LogoCandidate(
        provider="test",
        candidate_id=candidate_id,
        title="台灣角川 Logo",
        image_url=url or f"https://images.example/{candidate_id}.png",
        preview_url=url or f"https://images.example/{candidate_id}.png",
        source_page="https://www.kadokawa.com.tw/",
        source_category=source,
        source_domain="kadokawa.com.tw",
        width_px=width,
        height_px=height,
        media_type=media_type,
        transparent_background=transparent,
        official_source=official,
    )


def test_ranking_prefers_verified_official_transparent_vector_logo() -> None:
    profile = publisher_profile("台灣角川")
    candidates = (
        _candidate("other", source=LogoSourceCategory.OTHER, width=2000, height=1000),
        _candidate(
            "official-png",
            source=LogoSourceCategory.OFFICIAL,
            transparent=True,
            official=True,
        ),
        _candidate(
            "official-svg",
            source=LogoSourceCategory.OFFICIAL,
            transparent=True,
            media_type="image/svg+xml",
            official=True,
        ),
    )

    ranked = rank_logo_candidates(candidates, profile)

    assert [candidate.candidate_id for candidate in ranked] == [
        "official-svg",
        "official-png",
        "other",
    ]


def test_dedupe_collapses_equivalent_urls_and_keeps_higher_quality_candidate() -> None:
    low = _candidate(
        "low",
        source=LogoSourceCategory.OTHER,
        url="https://example.test/logo.png?width=200#fragment",
        width=200,
        height=80,
    )
    high = _candidate(
        "high",
        source=LogoSourceCategory.WIKIMEDIA,
        url="https://example.test/logo.png?width=200",
        width=1200,
        height=480,
        transparent=True,
    )

    result = dedupe_logo_candidates((low, high), publisher_profile("台灣角川"))

    assert result == (high,)


def test_logo_candidate_allows_http_or_https_but_rejects_other_schemes() -> None:
    http = _candidate(
        "http",
        source=LogoSourceCategory.OTHER,
        url="http://legacy.example/logo.png",
    )
    assert http.image_url.startswith("http://")

    try:
        _candidate(
            "file",
            source=LogoSourceCategory.OTHER,
            url="file:///tmp/logo.png",
        )
    except ValueError as exc:
        assert "HTTP" in str(exc)
    else:
        raise AssertionError("file:// must be rejected")


def test_unknown_cjk_publishers_get_distinct_stable_custom_ids() -> None:
    first = publisher_profile("甲出版社")
    second = publisher_profile("乙出版社")

    assert first.publisher_id.startswith("custom-")
    assert second.publisher_id.startswith("custom-")
    assert first.publisher_id != second.publisher_id
    assert publisher_profile("甲出版社").publisher_id == first.publisher_id
