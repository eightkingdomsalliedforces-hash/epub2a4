from __future__ import annotations

from pathlib import Path

from scripts.desktop_smoke import run_smoke


def test_desktop_cover_smoke(tmp_path: Path) -> None:
    result = run_smoke(tmp_path)

    assert result["route"] == "cover"
    assert Path(result["preview_path"]).is_file()
    assert Path(result["original_pdf_path"]).is_file()
    assert Path(result["print_pdf_path"]).is_file()
    assert Path(result["print_docx_path"]).is_file()
    assert result["original_pdf_path"].endswith("-完整書衣-原始尺寸.pdf")
    assert result["print_pdf_path"].endswith("-A4拼接列印.pdf")
    assert result["print_docx_path"].endswith("-A4拼接列印.docx")
