from __future__ import annotations

from pathlib import Path

from scripts.desktop_smoke import run_smoke


def test_desktop_cover_smoke(tmp_path: Path) -> None:
    result = run_smoke(tmp_path)

    assert result["route"] == "cover"
    assert Path(result["preview_path"]).is_file()
    assert Path(result["pdf_path"]).is_file()
    assert Path(result["docx_path"]).is_file()
    assert result["pdf_path"].endswith("_完整書封.pdf")
    assert result["docx_path"].endswith("_完整書封.docx")
