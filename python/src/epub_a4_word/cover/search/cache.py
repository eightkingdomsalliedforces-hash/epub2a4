from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.parse import urlsplit, urlunsplit

from .download import DownloadedImage


class ImageCache:
    def __init__(self, root: Path | str, max_bytes: int = 200 * 1024 * 1024) -> None:
        self.root = Path(root)
        self.max_bytes = int(max_bytes)
        self.files = self.root / "files"
        self.index_path = self.root / "index.json"
        self.files.mkdir(parents=True, exist_ok=True)
        self.index = self._load()
        self.reconcile()

    @staticmethod
    def key_for(url: str) -> str:
        parsed = urlsplit(url)
        normalized = urlunsplit(
            (parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path, parsed.query, "")
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            raw = json.loads(self.index_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def reconcile(self) -> None:
        changed = False
        for key in tuple(self.index):
            if not (self.files / key).is_file():
                del self.index[key]
                changed = True
        indexed = set(self.index)
        for path in self.files.iterdir():
            if path.is_file() and path.name not in indexed:
                path.unlink(missing_ok=True)
                changed = True
        if changed:
            self._write()

    def get(self, url: str) -> Path | None:
        key = self.key_for(url)
        path = self.files / key
        if not path.is_file() or key not in self.index:
            return None
        self.index[key]["accessed_at"] = time.time()
        self._write()
        return path

    def put(self, url: str, source: Path | str, metadata: DownloadedImage) -> Path:
        key = self.key_for(url)
        destination = self.files / key
        shutil.copyfile(source, destination)
        self.index[key] = {
            "size": destination.stat().st_size,
            "accessed_at": time.time(),
            "content_type": metadata.content_type,
            "width": metadata.width,
            "height": metadata.height,
        }
        self._evict()
        self._write()
        return destination

    def _evict(self) -> None:
        def total() -> int:
            return sum(int(item.get("size", 0)) for item in self.index.values())

        while self.index and total() > self.max_bytes:
            oldest = min(
                self.index,
                key=lambda key: float(self.index[key].get("accessed_at", 0.0)),
            )
            (self.files / oldest).unlink(missing_ok=True)
            del self.index[oldest]

    def _write(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.index, ensure_ascii=False, sort_keys=True),
            "utf-8",
        )
        os.replace(temporary, self.index_path)
