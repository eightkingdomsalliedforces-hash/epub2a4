"""Chaquopy-facing bridge for the offline Android application.

The public API intentionally uses only strings, primitive values and JSON so
it remains stable across the Kotlin/Python boundary.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from epub_a4_word import __version__ as CORE_VERSION
from epub_a4_word.converter import convert_input
from epub_a4_word.pagination import LayoutSettings

BRIDGE_VERSION = "1.0"
_SUPPORTED_INPUTS = {".epub": "epub", ".docx": "docx"}
_SUPPORTED_MODES = {
    "epub": ("signature16", "four_up", "single_a5", "single_4x6"),
    "docx": ("single_a5", "single_4x6"),
}
_SETTING_FIELDS = {
    "imposition_mode",
    "margin_mode",
    "font_name",
    "body_font_pt",
    "heading_font_pt",
    "line_spacing",
    "paragraph_spacing_pt",
    "page_numbers",
    "cut_guides",
}


class ConversionCancelled(RuntimeError):
    """Raised when the Android caller requests cancellation."""


class _ProgressAdapter:
    def __init__(self, callback: Any | None):
        self.callback = callback

    def cancelled(self) -> bool:
        if self.callback is None:
            return False
        checker = getattr(self.callback, "isCancelled", None)
        return bool(checker()) if checker is not None else False

    def check(self) -> None:
        if self.cancelled():
            raise ConversionCancelled("轉換已取消。")

    def __call__(self, percent: int, message: str) -> None:
        self.check()
        if self.callback is not None:
            reporter = getattr(self.callback, "onProgress", None)
            if reporter is not None:
                reporter(int(percent), str(message))


def probe() -> dict[str, Any]:
    return {
        "bridge_version": BRIDGE_VERSION,
        "python_core_version": CORE_VERSION,
        "supported_inputs": ["epub", "docx"],
        "supported_modes": {key: list(value) for key, value in _SUPPORTED_MODES.items()},
    }


def _decode_options(options_json: str | None) -> dict[str, Any]:
    if not options_json:
        return {}
    try:
        value = json.loads(options_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"設定 JSON 無效：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("設定 JSON 必須是物件。")
    unknown = sorted(set(value) - _SETTING_FIELDS)
    if unknown:
        raise ValueError("不支援的設定：" + "、".join(unknown))
    return value


def _validate_paths(input_path: str, output_path: str) -> tuple[Path, Path, str]:
    source = Path(input_path)
    output = Path(output_path)
    source_type = _SUPPORTED_INPUTS.get(source.suffix.lower())
    if source_type is None:
        raise ValueError("輸入檔案只支援 EPUB 或 DOCX。")
    if not source.is_file():
        raise ValueError("找不到輸入檔案。")
    if output.suffix.lower() != ".docx":
        raise ValueError("輸出檔案必須使用 .docx 副檔名。")
    if source.resolve() == output.resolve():
        raise ValueError("輸出路徑不可覆蓋原始文件。")
    output.parent.mkdir(parents=True, exist_ok=True)
    return source, output, source_type


def _settings_for(source_type: str, options: dict[str, Any]) -> LayoutSettings:
    if "imposition_mode" not in options:
        options = dict(options)
        options["imposition_mode"] = "signature16" if source_type == "epub" else "single_a5"
    mode = options["imposition_mode"]
    if mode not in _SUPPORTED_MODES[source_type]:
        if source_type == "docx":
            raise ValueError("DOCX 重新排版只支援 A5 或 4×6 英吋單頁模式。")
        raise ValueError("EPUB 輸出模式無效。")
    try:
        return LayoutSettings(**options)
    except TypeError as exc:
        raise ValueError(f"設定值無效：{exc}") from exc


def _result_dict(result: Any) -> dict[str, Any]:
    raw = asdict(result) if is_dataclass(result) else dict(vars(result))
    raw["output_path"] = str(raw["output_path"])
    raw["warnings"] = list(raw.get("warnings", ()))
    return raw


def convert_file(
    input_path: str,
    output_path: str,
    options_json: str = "{}",
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    source, output, source_type = _validate_paths(input_path, output_path)
    options = _decode_options(options_json)
    settings = _settings_for(source_type, options)
    progress = _ProgressAdapter(progress_callback)
    progress.check()
    result = convert_input(source, output, settings=settings, progress=progress)
    progress.check()
    return _result_dict(result)


def convert_file_json(
    input_path: str,
    output_path: str,
    options_json: str = "{}",
    progress_callback: Any | None = None,
) -> str:
    return json.dumps(
        convert_file(input_path, output_path, options_json, progress_callback),
        ensure_ascii=False,
        separators=(",", ":"),
    )
