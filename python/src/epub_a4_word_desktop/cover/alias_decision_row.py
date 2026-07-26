from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from epub_a4_word.cover.search.models import ResolvedAlias, alias_key


class AliasDecisionRow(QFrame):
    accepted = Signal(object)
    ignored = Signal(str)

    def __init__(
        self,
        alias: ResolvedAlias,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.alias = alias
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.value_label = QLabel(alias.value, self)
        self.value_label.setWordWrap(True)
        language = alias.language or "語言未知"
        source = alias.source or "來源未知"
        self.detail_label = QLabel(f"{language}｜{source}｜需要確認", self)
        self.reason_label = QLabel("；".join(alias.reasons) or "未提供比對理由", self)
        self.reason_label.setWordWrap(True)

        self.accept_button = QPushButton("確認並使用", self)
        self.ignore_button = QPushButton("忽略", self)
        self.accept_button.clicked.connect(
            lambda _checked=False: self.accepted.emit(self.alias)
        )
        self.ignore_button.clicked.connect(
            lambda _checked=False: self.ignored.emit(alias_key(self.alias))
        )

        actions = QHBoxLayout()
        actions.addWidget(self.accept_button)
        actions.addWidget(self.ignore_button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.reason_label)
        layout.addLayout(actions)
