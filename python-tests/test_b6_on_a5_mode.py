from pathlib import Path

import pytest

from epub_a4_word.imposition import build_imposition
from epub_a4_word_desktop.conversion.legacy_adapter import allowed_modes_for_path
from epub_a4_word_desktop.conversion.models import ConversionRequest, trim_size_for_mode


def test_b6_on_a5_is_epub_only_single_page_mode(tmp_path: Path) -> None:
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"placeholder")

    assert "b6_on_a5" in allowed_modes_for_path(epub)
    assert "b6_on_a5" not in allowed_modes_for_path(Path("book.docx"))
    assert build_imposition(3, "b6_on_a5").sides == ((1,), (2,), (3,))
    assert trim_size_for_mode("b6_on_a5") == (128.0, 182.0)

    request = ConversionRequest(
        input_path=epub,
        output_path=tmp_path / "book.docx",
        imposition_mode="b6_on_a5",
        output_mark_mode="crop_marks",
    )
    request.validate()
    assert request.to_layout_settings().output_mark_mode == "crop_marks"


@pytest.mark.parametrize("output_mark_mode", ["", "marks", "crop"])
def test_conversion_request_rejects_unknown_output_mark_mode(
    tmp_path: Path,
    output_mark_mode: str,
) -> None:
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"placeholder")
    request = ConversionRequest(
        input_path=epub,
        output_path=tmp_path / "book.docx",
        imposition_mode="b6_on_a5",
        output_mark_mode=output_mark_mode,
    )

    with pytest.raises(ValueError, match="列印標記"):
        request.validate()
