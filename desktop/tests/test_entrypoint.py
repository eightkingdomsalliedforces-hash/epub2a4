from __future__ import annotations

from unittest.mock import patch

from epub_a4_word_desktop.__main__ import main


def test_default_entry_starts_qt_application() -> None:
    with patch("epub_a4_word_desktop.__main__.run_qt_app", return_value=0) as run:
        assert main([]) == 0
        run.assert_called_once_with([])


def test_legacy_flag_starts_tkinter_compatibility_gui() -> None:
    with patch("epub_a4_word_desktop.__main__.run_legacy_gui", return_value=0) as run:
        assert main(["--legacy-gui"]) == 0
        run.assert_called_once_with()


def test_unknown_arguments_are_forwarded_to_qt() -> None:
    with patch("epub_a4_word_desktop.__main__.run_qt_app", return_value=0) as run:
        assert main(["--platform", "offscreen"]) == 0
        run.assert_called_once_with(["--platform", "offscreen"])
