from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


class Callback:
    def __init__(self, cancelled: bool = False):
        self.cancelled = cancelled
        self.events: list[tuple[int, str]] = []

    def onProgress(self, percent: int, message: str) -> None:
        self.events.append((percent, message))

    def isCancelled(self) -> bool:
        return self.cancelled


def test_probe_lists_android_supported_modes():
    import android_bridge

    result = android_bridge.probe()

    assert result["bridge_version"] == "1.0"
    assert result["python_core_version"] == "0.5.0"
    assert result["supported_inputs"] == ["epub", "docx"]
    assert result["supported_modes"]["docx"] == ["single_a5", "single_4x6"]


def test_convert_file_builds_settings_for_epub(monkeypatch, tmp_path: Path):
    import android_bridge

    source = tmp_path / "book.epub"
    source.write_bytes(b"fixture")
    output = tmp_path / "result.docx"
    captured = {}

    def fake_convert(input_path, output_path, settings, progress):
        captured.update(
            input_path=Path(input_path),
            output_path=Path(output_path),
            settings=settings,
        )
        progress(42, "排版中")
        output.write_bytes(b"docx")
        return SimpleNamespace(
            output_path=output,
            title="測試書",
            author="作者",
            mini_page_count=12,
            a4_page_count=4,
            image_count=3,
            warnings=("提醒",),
            imposition_mode=settings.imposition_mode,
            paper_sheet_count=2,
            signature_count=1,
            padded_mini_page_count=16,
            source_format="epub",
        )

    monkeypatch.setattr(android_bridge, "convert_input", fake_convert)
    callback = Callback()
    result = android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps(
            {
                "imposition_mode": "signature16",
                "margin_mode": "safe",
                "body_font_pt": 9.0,
                "page_numbers": True,
                "cut_guides": False,
            }
        ),
        callback,
    )

    assert captured["input_path"] == source
    assert captured["output_path"] == output
    assert captured["settings"].imposition_mode == "signature16"
    assert captured["settings"].margin_mode == "safe"
    assert captured["settings"].body_font_pt == 9.0
    assert callback.events == [(42, "排版中")]
    assert result["output_path"] == str(output)
    assert result["warnings"] == ["提醒"]
    assert result["signature_count"] == 1


def test_docx_rejects_booklet_mode(tmp_path: Path):
    import android_bridge

    source = tmp_path / "input.docx"
    source.write_bytes(b"fixture")

    with pytest.raises(ValueError, match="DOCX.*A5.*4×6"):
        android_bridge.convert_file(
            str(source),
            str(tmp_path / "out.docx"),
            json.dumps({"imposition_mode": "signature16"}),
        )


def test_unknown_option_is_rejected(tmp_path: Path):
    import android_bridge

    source = tmp_path / "input.epub"
    source.write_bytes(b"fixture")

    with pytest.raises(ValueError, match="不支援的設定"):
        android_bridge.convert_file(
            str(source),
            str(tmp_path / "out.docx"),
            json.dumps({"dangerous": True}),
        )


def test_cancellation_stops_before_conversion(monkeypatch, tmp_path: Path):
    import android_bridge

    source = tmp_path / "input.epub"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(
        android_bridge,
        "convert_input",
        lambda *args, **kwargs: pytest.fail("conversion must not start"),
    )

    with pytest.raises(android_bridge.ConversionCancelled, match="已取消"):
        android_bridge.convert_file(
            str(source),
            str(tmp_path / "out.docx"),
            "{}",
            Callback(cancelled=True),
        )


def test_convert_file_json_is_valid_json(monkeypatch, tmp_path: Path):
    import android_bridge

    source = tmp_path / "input.epub"
    source.write_bytes(b"fixture")
    output = tmp_path / "out.docx"

    monkeypatch.setattr(
        android_bridge,
        "convert_file",
        lambda *args, **kwargs: {"title": "中文", "warnings": [], "output_path": str(output)},
    )

    payload = json.loads(android_bridge.convert_file_json(str(source), str(output), "{}"))
    assert payload["title"] == "中文"


def test_real_docx_fixture_reflows_to_a5(tmp_path: Path):
    import android_bridge

    root = Path(__file__).resolve().parents[1]
    source = root / "test-fixtures" / "A4_test_document.docx"
    output = tmp_path / "a5.docx"

    result = android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps({"imposition_mode": "single_a5", "margin_mode": "maximized"}),
    )

    assert output.stat().st_size > 1000
    assert result["source_format"] == "docx"
    assert result["imposition_mode"] == "single_a5"


def test_real_epub_fixture_keeps_image_and_outputs_4x6(tmp_path: Path):
    import android_bridge

    root = Path(__file__).resolve().parents[1]
    source = root / "test-fixtures" / "minimal.epub"
    output = tmp_path / "photo.docx"

    result = android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps({"imposition_mode": "single_4x6", "margin_mode": "safe"}),
    )

    assert output.stat().st_size > 1000
    assert result["source_format"] == "epub"
    assert result["image_count"] == 1
    assert result["mini_page_count"] >= 1
