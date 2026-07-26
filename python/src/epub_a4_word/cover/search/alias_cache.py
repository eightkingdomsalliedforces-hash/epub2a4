from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .models import BookIdentity, ResolvedAlias
from .query_plan import normalize_isbn

_CACHE_VERSION = 1


def _identity_digest(identity: BookIdentity, *, include_volume: bool) -> str:
    parts = [identity.normalized_title.casefold(), identity.normalized_author.casefold()]
    if include_volume:
        parts.append(identity.volume)
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _alias_dict(alias: ResolvedAlias) -> dict[str, object]:
    return {
        "value": alias.value,
        "language": alias.language,
        "confidence": alias.confidence,
    }


def _merge_alias(raw_aliases: list[dict[str, object]], alias: ResolvedAlias) -> None:
    key = (alias.value.casefold().strip(), (alias.language or "").casefold())
    for index, raw in enumerate(raw_aliases):
        current = (
            str(raw.get("value", "")).casefold().strip(),
            str(raw.get("language") or "").casefold(),
        )
        if current == key:
            raw_aliases[index] = _alias_dict(alias)
            return
    raw_aliases.append(_alias_dict(alias))


class AliasCache:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _load_raw(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": _CACHE_VERSION, "books": {}, "series": {}}
        if not isinstance(raw, dict) or raw.get("version") != _CACHE_VERSION:
            return {"version": _CACHE_VERSION, "books": {}, "series": {}}
        books = raw.get("books") if isinstance(raw.get("books"), dict) else {}
        series = raw.get("series") if isinstance(raw.get("series"), dict) else {}
        return {"version": _CACHE_VERSION, "books": books, "series": series}

    def _write_raw(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True),
            "utf-8",
        )
        os.replace(temporary, self.path)

    def load(self, identity: BookIdentity) -> tuple[ResolvedAlias, ...]:
        raw = self._load_raw()
        book_key = (
            f"isbn:{identity.isbn}"
            if identity.isbn
            else f"identity:{_identity_digest(identity, include_volume=True)}"
        )
        series_key = f"series:{_identity_digest(identity, include_volume=False)}"
        entries = []
        for bucket_name, key in (("books", book_key), ("series", series_key)):
            bucket = raw[bucket_name]
            entry = bucket.get(key) if isinstance(bucket, dict) else None
            aliases = entry.get("aliases") if isinstance(entry, dict) else None
            if isinstance(aliases, list):
                entries.extend(item for item in aliases if isinstance(item, dict))
        result: list[ResolvedAlias] = []
        seen: set[tuple[str, str]] = set()
        for item in entries:
            value = str(item.get("value", "")).strip()
            language = str(item.get("language") or "").strip() or None
            key = (value.casefold(), (language or "").casefold())
            if not value or key in seen:
                continue
            seen.add(key)
            result.append(
                ResolvedAlias(
                    value=value,
                    language=language,
                    source="local_cache",
                    confidence=str(item.get("confidence") or "high"),
                    reasons=("本機已確認別名",),
                )
            )
        return tuple(result)

    def remember(
        self,
        identity: BookIdentity,
        alias: ResolvedAlias,
        isbn: str = "",
    ) -> None:
        if not alias.value.strip():
            return
        raw = self._load_raw()
        book_key = (
            f"isbn:{identity.isbn}"
            if identity.isbn
            else f"identity:{_identity_digest(identity, include_volume=True)}"
        )
        series_key = f"series:{_identity_digest(identity, include_volume=False)}"
        books = raw["books"]
        series = raw["series"]
        book_entry = books.setdefault(book_key, {"aliases": []})
        series_entry = series.setdefault(series_key, {"aliases": []})
        _merge_alias(book_entry.setdefault("aliases", []), alias)
        _merge_alias(series_entry.setdefault("aliases", []), alias)
        valid_isbn = normalize_isbn(isbn)
        if valid_isbn:
            book_entry["isbn"] = valid_isbn
        self._write_raw(raw)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
