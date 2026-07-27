from __future__ import annotations

from pathlib import Path

from epub_a4_word.cover import fonts


def test_android_root_fonts_are_discovered(monkeypatch, tmp_path: Path) -> None:
    android_root = tmp_path / "system"
    font_dir = android_root / "fonts"
    font_dir.mkdir(parents=True)
    fake_font = font_dir / "NotoSansCJK-Regular.ttc"
    fake_font.write_bytes(b"font-placeholder")

    monkeypatch.setenv("ANDROID_ROOT", str(android_root))
    fonts._installed_font_files.cache_clear()

    assert font_dir in fonts._font_directories()
    assert fake_font in fonts._installed_font_files()


def test_generic_sans_request_does_not_preempt_cjk_default_candidates() -> None:
    from epub_a4_word.cover.typography import font_candidates

    candidates = font_candidates("default", "sans-serif")

    assert candidates.index("Noto Sans CJK TC") < candidates.index("sans-serif")
