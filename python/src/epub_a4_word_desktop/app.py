from __future__ import annotations

from collections.abc import Sequence


def _application(argv: Sequence[str] | None = None):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    existing = QApplication.instance()
    app = existing or QApplication(["epub2a4-desktop", *(list(argv) if argv else [])])
    QCoreApplication.setApplicationName("EPUB／Word 排版與封面工具")
    QCoreApplication.setOrganizationName("epub2a4")
    return app, existing is None


def run(argv: Sequence[str] | None = None) -> int:
    """Start the PySide6 desktop application."""

    from .main_window import MainWindow

    app, owns_application = _application(argv)
    window = MainWindow()
    window.show()
    if not owns_application:
        return 0
    return app.exec()


def run_portable_smoke(argv: Sequence[str] | None = None) -> int:
    """Create the packaged Qt window, exercise routes, then exit immediately."""

    from .main_window import AppRoute, MainWindow

    app, owns_application = _application(argv)
    window = MainWindow()
    window.show()
    app.processEvents()

    expected_routes = {AppRoute.HOME, AppRoute.CONVERTER, AppRoute.COVER}
    if set(window.pages) != expected_routes:
        window.close()
        if owns_application:
            app.quit()
        return 2

    for route in (AppRoute.HOME, AppRoute.CONVERTER, AppRoute.COVER):
        window.navigate(route)
        app.processEvents()
        if window.current_route is not route:
            window.close()
            if owns_application:
                app.quit()
            return 3

    window.close()
    app.processEvents()
    if owns_application:
        app.quit()
    return 0
