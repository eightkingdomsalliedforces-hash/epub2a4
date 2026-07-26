from __future__ import annotations

from epub_a4_word_desktop.window_geometry import fit_initial_window


def test_initial_window_never_exceeds_available_screen() -> None:
    geometry = fit_initial_window(
        available_x=0,
        available_y=0,
        available_width=1366,
        available_height=728,
    )

    assert geometry.width <= 1366
    assert geometry.height <= 728
    assert geometry.x >= 0
    assert geometry.y >= 0
    assert geometry.x + geometry.width <= 1366
    assert geometry.y + geometry.height <= 728


def test_initial_window_keeps_desktop_target_on_large_screen() -> None:
    geometry = fit_initial_window(
        available_x=100,
        available_y=40,
        available_width=1920,
        available_height=1040,
    )

    assert geometry.width == 1280
    assert geometry.height == 820
    assert geometry.x == 420
    assert geometry.y == 150