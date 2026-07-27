from __future__ import annotations

import base64
import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from ..publisher_directory import PublisherProfile, publisher_profile
from .logo_http import LogoHttpClient
from .logo_models import LogoCandidate, LogoSearchPage, LogoSourceCategory
from .logo_ranking import dedupe_logo_candidates

_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_WIKIPEDIA_API = "https://zh.wikipedia.org/w/api.php"


def _token_encode(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _token_decode(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Logo 分頁代碼無效。") from exc
    if not isinstance(raw, dict):
        raise ValueError("Logo 分頁代碼無效。")
    return raw


def _metadata_value(raw: object) -> str:
    if isinstance(raw, dict):
        return re.sub(r"<[^>]+>", "", str(raw.get("value", ""))).strip()
    return ""


class _LogoHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {str(key).casefold(): str(value or "") for key, value in attrs}
        if tag.casefold() == "img":
            url = values.get("src") or values.get("data-src")
            text = " ".join((values.get("alt", ""), values.get("class", ""), values.get("id", "")))
        elif tag.casefold() == "link" and "icon" in values.get("rel", "").casefold():
            url = values.get("href")
            text = values.get("rel", "")
        else:
            return
        if url and any(word in (url + " " + text).casefold() for word in ("logo", "brand", "mark")):
            self.results.append((urljoin(self.base_url, url), text.strip() or "Official logo"))


class PublisherLogoSearch:
    def __init__(self, http=None) -> None:
        self.http = http or LogoHttpClient()

    def _official_candidates(self, profile: PublisherProfile) -> list[LogoCandidate]:
        get_text = getattr(self.http, "get_text", None)
        if get_text is None:
            return []
        results: list[LogoCandidate] = []
        for source_url in profile.official_urls:
            try:
                html = get_text(source_url, max_bytes=2 * 1024 * 1024)
            except Exception:
                continue
            parser = _LogoHtmlParser(source_url)
            parser.feed(html)
            for index, (image_url, title) in enumerate(parser.results[:20]):
                if urlsplit(image_url).scheme.casefold() not in {"http", "https"}:
                    continue
                host = urlsplit(source_url).hostname or ""
                results.append(
                    LogoCandidate(
                        provider="official_site",
                        candidate_id=hashlib.sha256(image_url.encode()).hexdigest()[:16],
                        title=title or f"{profile.display_name} Logo",
                        image_url=image_url,
                        preview_url=image_url,
                        source_page=source_url,
                        source_category=LogoSourceCategory.OFFICIAL,
                        source_domain=host,
                        official_source=True,
                    )
                )
        return results

    def _commons_candidates(
        self,
        query: str,
        *,
        limit: int,
        offset: int | None,
    ) -> tuple[list[LogoCandidate], int | None]:
        params: dict[str, object] = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": f'"{query}" logo',
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 480,
        }
        if offset is not None:
            params["gsroffset"] = offset
        raw = self.http.get_json(_COMMONS_API, params)
        pages = raw.get("query", {}).get("pages", []) if isinstance(raw.get("query"), dict) else []
        results: list[LogoCandidate] = []
        for page in pages if isinstance(pages, list) else []:
            if not isinstance(page, dict):
                continue
            infos = page.get("imageinfo", [])
            info = infos[0] if isinstance(infos, list) and infos and isinstance(infos[0], dict) else None
            if info is None or not str(info.get("url", "")):
                continue
            metadata = info.get("extmetadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            title = str(page.get("title", "Logo")).removeprefix("File:")
            results.append(
                LogoCandidate(
                    provider="wikimedia_commons",
                    candidate_id=str(page.get("pageid", title)),
                    title=title,
                    image_url=str(info.get("url", "")),
                    preview_url=str(info.get("thumburl") or info.get("url", "")),
                    source_page=f"https://commons.wikimedia.org/wiki/{str(page.get('title', '')).replace(' ', '_')}",
                    source_category=LogoSourceCategory.WIKIMEDIA,
                    source_domain="commons.wikimedia.org",
                    width_px=int(info["width"]) if info.get("width") else None,
                    height_px=int(info["height"]) if info.get("height") else None,
                    media_type=str(info.get("mime", "")),
                    transparent_background=(
                        True if str(info.get("mime", "")).casefold() in {"image/svg+xml", "image/png"} else None
                    ),
                    license_text=_metadata_value(metadata.get("LicenseShortName")),
                )
            )
        continuation = raw.get("continue", {})
        next_offset = (
            int(continuation["gsroffset"])
            if isinstance(continuation, dict) and continuation.get("gsroffset") is not None
            else None
        )
        return results, next_offset

    def _wikipedia_candidates(self, query: str, *, limit: int) -> list[LogoCandidate]:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 0,
            "gsrlimit": min(limit, 10),
            "prop": "pageimages|info",
            "piprop": "original|thumbnail",
            "pithumbsize": 480,
            "inprop": "url",
        }
        try:
            raw = self.http.get_json(_WIKIPEDIA_API, params)
        except Exception:
            return []
        query_raw = raw.get("query")
        pages = query_raw.get("pages", []) if isinstance(query_raw, dict) else []
        results: list[LogoCandidate] = []
        for page in pages if isinstance(pages, list) else []:
            if not isinstance(page, dict):
                continue
            original = page.get("original") if isinstance(page.get("original"), dict) else {}
            thumb = page.get("thumbnail") if isinstance(page.get("thumbnail"), dict) else {}
            image_url = str(original.get("source") or thumb.get("source") or "")
            if not image_url:
                continue
            results.append(
                LogoCandidate(
                    provider="wikipedia",
                    candidate_id=str(page.get("pageid", page.get("title", ""))),
                    title=f"{page.get('title', query)} Logo",
                    image_url=image_url,
                    preview_url=str(thumb.get("source") or image_url),
                    source_page=str(page.get("canonicalurl") or page.get("fullurl") or "https://zh.wikipedia.org/"),
                    source_category=LogoSourceCategory.WIKIPEDIA,
                    source_domain="wikipedia.org",
                    width_px=int(original["width"]) if original.get("width") else None,
                    height_px=int(original["height"]) if original.get("height") else None,
                )
            )
        return results

    def search(
        self,
        query: str,
        *,
        profile: PublisherProfile | None = None,
        page_token: str | None = None,
        limit: int = 20,
    ) -> LogoSearchPage:
        name = str(query).strip()
        if not name:
            raise ValueError("請輸入出版社名稱。")
        if not 1 <= int(limit) <= 20:
            raise ValueError("每頁 Logo 候選數必須介於 1 與 20。")
        selected_profile = profile or publisher_profile(name)
        token = _token_decode(page_token)
        offset_value = token.get("commons_offset")
        offset = int(offset_value) if offset_value is not None else None
        warnings: list[str] = []
        candidates: list[LogoCandidate] = []
        if not page_token:
            candidates.extend(self._official_candidates(selected_profile))
        try:
            commons, next_offset = self._commons_candidates(name, limit=limit, offset=offset)
            candidates.extend(commons)
        except Exception as exc:
            next_offset = None
            warnings.append(f"Wikimedia Commons：{exc}")
        if not page_token and len(candidates) < limit:
            candidates.extend(self._wikipedia_candidates(name, limit=limit - len(candidates)))
        ranked = dedupe_logo_candidates(candidates, selected_profile)[:limit]
        next_token = _token_encode({"commons_offset": next_offset}) if next_offset is not None else None
        return LogoSearchPage(tuple(ranked), next_token, tuple(warnings))
