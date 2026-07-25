from __future__ import annotations

from pathlib import Path
from threading import Event
from unittest.mock import patch

import pytest

from epub_a4_word.converter import ConversionResult
from epub_a4_word_desktop.conversion.controller import (
    ConversionController,
    ConversionWorker,
)
from epub_a4_word_desktop.conversion.models import (
    ConversionRequest,
    completion_payload,
)


class ImmediatePool:
    def start(self, worker) -> None:
        worker.run()


class HoldingPool:
    def __init__(self) -> None:
        self.worker = None

    def start(self, worker) -> None:
        self.worker = worker


def make_request(tmp_path: Path, suffix: str = ".epub", mode: str = "signature16") -> ConversionRequest:
    source = tmp_path / f"book{suffix}"
    source.write_bytes(b"fixture")
    return ConversionRequest(
        input_path=source,
        output_path=tmp_path / "output.docx",
        imposition_mode=mode,
        margin_mode="safe",
        font_name="Noto Serif CJK TC",
        body_font_pt=9.0,
        heading_font_pt=14.0,
        page_numbers=True,
        cut_guides=True,
    )


def make_result(output_path: Path, *, pages: int = 37, mode: str = "signature16") -> ConversionResult:
    return ConversionResult(
        output_path=output_path,
        title="測試書名",
        author="測試作者",
        mini_page_count=pages,
        a4_page_count=10,
        image_count=2,
        warnings=("測試警告",),
        imposition_mode=mode,
        paper_sheet_count=5,
        signature_count=1,
        padded_mini_page_count=40,
    )


def test_docx_rejects_signature_mode(tmp_path: Path) -> None:
    request = make_request(tmp_path, suffix=".docx", mode="signature16")
    with pytest.raises(ValueError, match="DOCX"):
        request.validate()


def test_request_maps_all_layout_settings(tmp_path: Path) -> None:
    request = make_request(tmp_path, mode="four_up")
    settings = request.to_layout_settings()
    assert settings.imposition_mode == "four_up"
    assert settings.margin_mode == "safe"
    assert settings.font_name == "Noto Serif CJK TC"
    assert settings.body_font_pt == 9.0
    assert settings.heading_font_pt == 14.0
    assert settings.page_numbers is True
    assert settings.cut_guides is True


def test_epub_completion_payload_uses_actual_page_count(tmp_path: Path) -> None:
    request = make_request(tmp_path, mode="single_a5")
    result = make_result(request.output_path, pages=123, mode="single_a5")
    payload = completion_payload(request, result)
    assert payload["page_count"] == 123
    assert payload["trim_size_mm"] == {"width_mm": 148.0, "height_mm": 210.0}
    assert payload["source_path"] == str(request.input_path)
    assert payload["output_path"] == str(request.output_path)


def test_controller_emits_completion_with_cover_payload(qtbot, tmp_path: Path) -> None:
    request = make_request(tmp_path, mode="single_4x6")
    result = make_result(request.output_path, pages=52, mode="single_4x6")
    controller = ConversionController(pool=ImmediatePool())

    with patch(
        "epub_a4_word_desktop.conversion.controller.convert_input",
        return_value=result,
    ):
        with qtbot.waitSignal(controller.completed) as signal:
            controller.start(request)

    completion = signal.args[0]
    assert completion.actual_page_count == 52
    assert completion.trim_size_mm == (101.6, 152.4)
    assert completion.to_cover_payload()["title"] == "測試書名"


def test_worker_emits_cancelled_when_event_is_set(qtbot, tmp_path: Path) -> None:
    request = make_request(tmp_path)
    cancelled = Event()
    cancelled.set()
    worker = ConversionWorker(request, cancelled)

    with patch("epub_a4_word_desktop.conversion.controller.convert_input") as convert:
        with qtbot.waitSignal(worker.signals.cancelled):
            worker.run()

    convert.assert_not_called()


def test_controller_cancel_marks_held_worker_cancelled(qtbot, tmp_path: Path) -> None:
    pool = HoldingPool()
    controller = ConversionController(pool=pool)
    request = make_request(tmp_path)
    controller.start(request)
    assert controller.is_running is True
    controller.cancel()
    assert pool.worker is not None

    with qtbot.waitSignal(controller.cancelled):
        pool.worker.run()

    assert controller.is_running is False
