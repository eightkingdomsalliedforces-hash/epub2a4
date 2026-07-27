from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.parse import urlsplit, urlunsplit

from .logo_download import DownloadedLogo


class LogoCache:
    def __init__(self, root: Path | str, max_bytes: int = 100 * 1024 * 1024) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = int(max_bytes)
        self.files = self.root / "files"
        self.index_path = self.root / "index.json"
        self.files.mkdir(parents=True, exist_ok=True)
        self.index = self._load()
        self._reconcile()

    @staticmethod
    def key_for(url: str) -> str:
        parsed = urlsplit(url)
        normalized = urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path, parsed.query, ""))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            raw = json.loads(self.index_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _reconcile(self) -> None:
        changed = False
        for key, metadata in tuple(self.index.items()):
            filename = str(metadata.get("filename", ""))
            if not filename or not (self.files / filename).is_file():
                self.index.pop(key, None)
                changed = True
        if changed:
            self._write()

    def get(self, url: str) -> Path | None:
        key = self.key_for(url)
        metadata = self.index.get(key)
        if metadata is None:
            return None
        path = self.files / str(metadata.get("filename", ""))
        if not path.is_file():
            self.index.pop(key, None)
            self._write()
            return None
        metadata["accessed_at"] = time.time()
        self._write()
        return path

    def put(self, url: str, downloaded: DownloadedLogo) -> Path:
        key = self.key_for(url)
        filename = f"{key}{downloaded.path.suffix.casefold()}"
        destination = self.files / filename
        if downloaded.path.resolve() != destination.resolve():
            shutil.copyfile(downloaded.path, destination)
        self.index[key] = {
            "filename": filename,
            "size": destination.stat().st_size,
            "accessed_at": time.time(),
            "content_type": downloaded.content_type,
            "width": downloaded.width_px,
            "height": downloaded.height_px,
            "sha256": downloaded.sha256,
        }
        self._evict()
        self._write()
        return destination

    def _evict(self) -> None:
        def total() -> int:
            return sum(int(item.get("size", 0)) for item in self.index.values())
        while self.index and total() > self.max_bytes:
            oldest = min(self.index, key=lambda key: float(self.index[key].get("accessed_at", 0.0)))
            filename = str(self.index[oldest].get("filename", ""))
            (self.files / filename).unlink(missing_ok=True)
            self.index.pop(oldest, None)

    def _write(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.index, ensure_ascii=False, sort_keys=True), "utf-8")
        os.replace(temporary, self.index_path)
