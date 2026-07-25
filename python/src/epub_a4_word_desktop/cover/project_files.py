from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from epub_a4_word.cover.models import ElementKind
from epub_a4_word.cover.project_io import dumps_project, loads_project


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", Path(name).name).strip("._")
    return safe or "image"


def _asset_destination(source: Path, assets_dir: Path) -> Path:
    if not source.is_file():
        raise ValueError(f"找不到封面圖片：{source}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return assets_dir / f"{digest[:16]}-{_safe_name(source.name)}"


def save_project_bundle(project_json: str, destination: Path | str) -> Path:
    """Save a portable .cover.json and copy image assets beside it."""

    project = loads_project(project_json)
    output = Path(destination).expanduser().resolve()
    if not output.name.endswith(".cover.json"):
        raise ValueError("封面專案副檔名必須是 .cover.json。")
    output.parent.mkdir(parents=True, exist_ok=True)
    assets_dir = output.parent / f"{output.stem}_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    raw: dict[str, Any] = json.loads(dumps_project(project))
    for element in raw.get("elements", []):
        if element.get("kind") != ElementKind.IMAGE.value:
            continue
        content = element.get("content")
        if not isinstance(content, dict):
            continue
        source = Path(str(content.get("path"))).expanduser().resolve()
        target = _asset_destination(source, assets_dir)
        if not target.exists():
            temporary_asset = target.with_suffix(target.suffix + ".tmp")
            try:
                shutil.copyfile(source, temporary_asset)
                temporary_asset.replace(target)
            finally:
                temporary_asset.unlink(missing_ok=True)
        content["path"] = target.relative_to(output.parent).as_posix()

    raw["working_dir"] = "."
    serialized = json.dumps(
        raw,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def open_project_bundle(path: Path | str) -> str:
    """Open a portable project, resolving assets against the project folder."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"找不到封面專案：{source}")
    try:
        raw = json.loads(source.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"無法開啟封面專案：{source}") from exc
    if not isinstance(raw, dict):
        raise ValueError("封面專案 JSON 必須是物件。")

    for element in raw.get("elements", []):
        if (
            not isinstance(element, dict)
            or element.get("kind") != ElementKind.IMAGE.value
        ):
            continue
        content = element.get("content")
        if not isinstance(content, dict):
            continue
        path_value = content.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("封面圖片路徑無效。")
        asset = Path(path_value).expanduser()
        if not asset.is_absolute():
            asset = source.parent / asset
        asset = asset.resolve()
        if not asset.is_file():
            raise ValueError(f"找不到封面圖片：{asset}")
        content["path"] = str(asset)

    working_dir = Path(str(raw.get("working_dir", "."))).expanduser()
    if not working_dir.is_absolute():
        working_dir = source.parent / working_dir
    raw["working_dir"] = str(working_dir.resolve())
    return dumps_project(loads_project(json.dumps(raw, ensure_ascii=False)))
