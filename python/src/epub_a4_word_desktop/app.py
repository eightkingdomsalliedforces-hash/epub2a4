from __future__ import annotations

from collections.abc import Sequence


def run(argv: Sequence[str] | None = None) -> int:
    """Start the PySide6 desktop application."""

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    existing = QApplication.instance()
    owns_application = existing is None
    app = existing or QApplication(["epub2a4-desktop", *(list(argv) if argv else [])])

    QCoreApplication.setApplicationName("EPUB／Word 排版與封面工具")
    QCoreApplication.setOrganizationName("epub2a4")

    window = MainWindow()
    window.show()
    if not owns_application:
        return 0
    return app.exec()
