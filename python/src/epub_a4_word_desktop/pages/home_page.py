from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class HomePage(QWidget):
    open_converter = Signal()
    open_cover = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("home-page")

        title = QLabel("EPUB／Word 排版與封面工具", self)
        title.setObjectName("home-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "將 EPUB／Word 重新排版，或建立可列印、可編輯的完整書封。",
            self,
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.converter_button = QPushButton("轉換 EPUB／Word", self)
        self.converter_button.setObjectName("open-converter-button")
        self.converter_button.clicked.connect(self.open_converter.emit)

        self.cover_button = QPushButton("封面工具", self)
        self.cover_button.setObjectName("open-cover-button")
        self.cover_button.clicked.connect(self.open_cover.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(96, 72, 96, 72)
        layout.setSpacing(18)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(16)
        layout.addWidget(self.converter_button)
        layout.addWidget(self.cover_button)
        layout.addStretch(1)
