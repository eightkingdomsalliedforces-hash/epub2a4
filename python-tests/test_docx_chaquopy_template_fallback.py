from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from docx import Document


def test_inline_header_footer_templates_work_without_package_files(tmp_path: Path) -> None:
    from epub_a4_word.docx_compat import install_story_template_fallbacks

    install_story_template_fallbacks(force=True)

    output = tmp_path / "fallback.docx"
    document = Document()
    section = document.sections[0]
    section.header.paragraphs[0].add_run("guide")
    section.footer.paragraphs[0].add_run("page")
    document.save(output)

    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "word/header1.xml" in names
        assert "word/footer1.xml" in names
        assert b"guide" in archive.read("word/header1.xml")
        assert b"page" in archive.read("word/footer1.xml")
