from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .converter_page import ConverterPage
from .home_page import HomePage


class CoverPage(QWidget):
    """Cover-tool landing page used until the visual editor is added."""

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cover-page")
        self.conversion_payload: dict[str, object] | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("完整書封工具", self))

    def open_from_conversion(self, payload: Mapping[str, object]) -> None:
        self.conversion_payload = dict(payload)


__all__ = ["CoverPage", "ConverterPage", "HomePage"]
