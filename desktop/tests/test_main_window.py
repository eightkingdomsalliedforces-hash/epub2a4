from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from epub_a4_word_desktop.main_window import AppRoute, MainWindow


def test_home_is_initial_route(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.current_route is AppRoute.HOME
    assert window.stack.currentWidget().objectName() == "home-page"


def test_navigation_switches_to_cover_page(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigate(AppRoute.COVER)
    assert window.current_route is AppRoute.COVER
    assert window.stack.currentWidget().objectName() == "cover-page"


def test_home_buttons_open_converter_and_cover(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)

    qtbot.mouseClick(window.home_page.converter_button, Qt.MouseButton.LeftButton)
    assert window.current_route is AppRoute.CONVERTER

    window.navigate(AppRoute.HOME)
    qtbot.mouseClick(window.home_page.cover_button, Qt.MouseButton.LeftButton)
    assert window.current_route is AppRoute.COVER


def test_valid_conversion_payload_is_delivered_to_cover_page(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    payload = {
        "source_path": "/tmp/book.epub",
        "page_count": 160,
        "trim_size_mm": {"width_mm": 105.0, "height_mm": 148.0},
    }
    window.navigate(AppRoute.COVER, payload)
    assert window.cover_page.conversion_payload == payload
    assert window.current_route is AppRoute.COVER


def test_invalid_conversion_payload_does_not_switch_route(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    with pytest.raises(ValueError, match="缺少"):
        window.navigate(AppRoute.COVER, {"source_path": "/tmp/book.epub"})
    assert window.current_route is AppRoute.HOME


def test_cover_sidebars_are_scrollable_instead_of_forcing_window_height(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.cover_page.left_scroll.widgetResizable()
    assert window.cover_page.right_scroll.widgetResizable()
