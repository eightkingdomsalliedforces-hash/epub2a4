from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def test_android_probe_exposes_b6_on_a5_for_epub_and_docx() -> None:
    import android_bridge

    supported = android_bridge.probe()["supported_modes"]

    assert "b6_on_a5" in supported["epub"]
    assert "b6_on_a5" in supported["docx"]


def test_android_bridge_forwards_b6_crop_mark_settings(monkeypatch, tmp_path: Path) -> None:
    import android_bridge

    source = tmp_path / "book.docx"
    source.write_bytes(b"fixture")
    output = tmp_path / "b6.docx"
    captured = {}

    def fake_convert(input_path, output_path, settings, progress, *, content_only=True):
        captured["mode"] = settings.imposition_mode
        captured["mark_mode"] = settings.output_mark_mode
        output.write_bytes(b"docx")
        return SimpleNamespace(
            output_path=output,
            title="",
            author="",
            mini_page_count=1,
            a4_page_count=1,
            image_count=0,
            warnings=(),
            imposition_mode=settings.imposition_mode,
            paper_sheet_count=1,
            signature_count=0,
            padded_mini_page_count=1,
            source_format="docx",
        )

    monkeypatch.setattr(android_bridge, "convert_input", fake_convert)

    android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps(
            {
                "imposition_mode": "b6_on_a5",
                "output_mark_mode": "crop_marks",
                "cut_guides": True,
            }
        ),
    )

    assert captured == {"mode": "b6_on_a5", "mark_mode": "crop_marks"}
