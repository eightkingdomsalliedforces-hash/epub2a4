from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from epub_a4_word_desktop import legacy_gui
from epub_a4_word_desktop.conversion.legacy_adapter import (
    ConversionCancelled,
    LegacyConversionRequest,
    allowed_modes_for_path,
    run_conversion,
)


def test_legacy_epub_modes_are_preserved() -> None:
    assert allowed_modes_for_path(Path("book.epub")) == (
        "signature16",
        "four_up",
        "single_a5",
        "single_4x6",
    )


def test_legacy_docx_modes_are_preserved() -> None:
    assert allowed_modes_for_path(Path("book.docx")) == ("single_a5", "single_4x6")


def test_unknown_source_has_no_conversion_modes() -> None:
    assert allowed_modes_for_path(Path("book.pdf")) == ()


def test_run_conversion_delegates_to_shared_core(tmp_path: Path) -> None:
    request = LegacyConversionRequest(
        input_path=tmp_path / "book.epub",
        output_path=tmp_path / "book.docx",
        imposition_mode="four_up",
        margin_mode="safe",
        font_name="Noto Serif CJK TC",
        body_font_pt=9.0,
        heading_font_pt=14.0,
        page_numbers=False,
        cut_guides=True,
    )
    sentinel = object()

    with patch(
        "epub_a4_word_desktop.conversion.legacy_adapter.convert_input",
        return_value=sentinel,
    ) as convert:
        assert run_conversion(request) is sentinel

    input_path, output_path, settings, callback = convert.call_args.args
    assert input_path == request.input_path
    assert output_path == request.output_path
    assert settings.imposition_mode == "four_up"
    assert settings.margin_mode == "safe"
    assert settings.body_font_pt == 9.0
    assert settings.heading_font_pt == 14.0
    assert settings.page_numbers is False
    assert settings.cut_guides is True
    assert callable(callback)


def test_cancelled_request_stops_before_shared_conversion(tmp_path: Path) -> None:
    request = LegacyConversionRequest(
        input_path=tmp_path / "book.epub",
        output_path=tmp_path / "book.docx",
        imposition_mode="signature16",
        margin_mode="safe",
        font_name="Noto Serif CJK TC",
        body_font_pt=9.0,
        heading_font_pt=14.0,
        page_numbers=True,
        cut_guides=True,
    )
    with patch("epub_a4_word_desktop.conversion.legacy_adapter.convert_input") as convert:
        with pytest.raises(ConversionCancelled, match="取消"):
            run_conversion(request, cancelled=lambda: True)
    convert.assert_not_called()


def test_legacy_gui_module_does_not_import_pyside6() -> None:
    assert "PySide6" not in inspect.getsource(legacy_gui)
