from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

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
    assert result["python_core_version"] == "0.7.0"
    assert result["supported_inputs"] == ["epub", "docx"]
    assert result["supported_modes"]["docx"] == [
        "single_a5",
        "b6_on_a5",
        "single_4x6",
    ]


def test_convert_file_builds_settings_for_epub(monkeypatch, tmp_path: Path):
    import android_bridge

    source = tmp_path / "book.epub"
    source.write_bytes(b"fixture")
    output = tmp_path / "result.docx"
    captured = {}

    def fake_convert(input_path, output_path, settings, progress, *, content_only=True):
        captured.update(
            input_path=Path(input_path),
            output_path=Path(output_path),
            settings=settings,
            content_only=content_only,
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
                "writing_mode": "taiwan_vertical",
                "binding_direction": "right",
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
    assert captured["settings"].writing_mode == "taiwan_vertical"
    assert captured["settings"].binding_direction == "right"
    assert captured["content_only"] is True
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("writing_mode", "diagonal", "writing mode"),
        ("binding_direction", "middle", "binding direction"),
    ],
)
def test_invalid_direction_option_is_rejected_before_conversion(
    monkeypatch,
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    import android_bridge

    source = tmp_path / "input.epub"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(
        android_bridge,
        "convert_input",
        lambda *args, **kwargs: pytest.fail("conversion must not start"),
    )

    with pytest.raises(ValueError, match=message):
        android_bridge.convert_file(
            str(source),
            str(tmp_path / "out.docx"),
            json.dumps({field: value}),
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


def test_cover_bridge_wrappers_return_compact_json(monkeypatch, tmp_path: Path):
    import android_bridge

    monkeypatch.setattr(
        android_bridge.cover_service,
        "inspect_source",
        lambda source_path: {"source_type": "epub", "title": "中文"},
    )
    monkeypatch.setattr(
        android_bridge.cover_service,
        "new_project",
        lambda source_path, settings_json: '{"schema_version":1}',
    )
    monkeypatch.setattr(
        android_bridge.cover_service,
        "apply_template",
        lambda project_json, template_id: '{"template":"minimal_text"}',
    )
    monkeypatch.setattr(
        android_bridge.cover_service,
        "render_preview",
        lambda project_json, output_png, max_px=1600: {
            "path": output_png,
            "width_px": 800,
            "height_px": 600,
        },
    )
    monkeypatch.setattr(
        android_bridge.cover_service,
        "export_cover",
        lambda project_json, pdf_path, docx_path, dpi=300: {
            "pdf": {"path": pdf_path},
            "docx": {"path": docx_path},
            "dpi": dpi,
        },
    )

    assert json.loads(android_bridge.cover_inspect_source_json("book.epub"))["title"] == "中文"
    assert json.loads(android_bridge.cover_new_project_json("book.epub", "{}"))["schema_version"] == 1
    assert json.loads(android_bridge.cover_apply_template_json("{}", "minimal_text"))["template"] == "minimal_text"
    assert json.loads(android_bridge.cover_render_preview_json("{}", str(tmp_path / "p.png"), 900))["width_px"] == 800
    assert json.loads(android_bridge.cover_export_json("{}", "a.pdf", "a.docx", 200))["dpi"] == 200


def test_android_bridge_passes_body_only_choice_to_epub_conversion(monkeypatch, tmp_path: Path):
    import android_bridge

    source = tmp_path / "book.epub"
    source.write_bytes(b"fixture")
    output = tmp_path / "result.docx"
    captured = {}

    def fake_convert(input_path, output_path, settings, progress, *, content_only=True):
        captured["content_only"] = content_only
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
            source_format="epub",
        )

    monkeypatch.setattr(android_bridge, "convert_input", fake_convert)

    android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps({"imposition_mode": "single_a5", "content_only": False}),
    )

    assert captured["content_only"] is False


def test_android_bridge_long_mixed_epub_uses_safe_a5_pagination(tmp_path: Path):
    import android_bridge

    source = tmp_path / "long-mixed.epub"
    output = tmp_path / "long-mixed-a5.docx"
    container_xml = """<?xml version='1.0'?>
    <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
      <rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>
    </container>"""
    opf = """<?xml version='1.0' encoding='utf-8'?>
    <package xmlns='http://www.idpf.org/2007/opf' version='3.0'>
      <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>
        <dc:title>Android 安全分頁測試</dc:title>
        <dc:creator>測試作者</dc:creator>
        <dc:language>zh-TW</dc:language>
      </metadata>
      <manifest>
        <item id='chapter' href='Text/chapter.xhtml' media-type='application/xhtml+xml'/>
      </manifest>
      <spine><itemref idref='chapter'/></spine>
    </package>"""
    paragraph = "魔法禁書目錄 A Certain Magical Index 中文 English 日本語 mixed text。" * 180
    chapter = (
        "<html xmlns='http://www.w3.org/1999/xhtml'><body>"
        "<h1>安全分頁</h1><p>" + paragraph + "</p>"
        "</body></html>"
    )
    with ZipFile(source, "w") as package:
        package.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        package.writestr("META-INF/container.xml", container_xml, compress_type=ZIP_DEFLATED)
        package.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
        package.writestr("OEBPS/Text/chapter.xhtml", chapter, compress_type=ZIP_DEFLATED)

    result = android_bridge.convert_file(
        str(source),
        str(output),
        json.dumps(
            {
                "imposition_mode": "single_a5",
                "margin_mode": "maximized",
                "content_only": True,
            }
        ),
    )

    assert output.stat().st_size > 1000
    assert result["source_format"] == "epub"
    assert result["imposition_mode"] == "single_a5"
    assert result["mini_page_count"] > 1
    assert result["warnings"] == []
