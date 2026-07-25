from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from epub_a4_word.cover.search.models import ProviderCredential


class CredentialDialog(QDialog):
    credential_chosen = Signal(object, str)
    clear_requested = Signal()

    def __init__(
        self,
        initial: ProviderCredential | None = None,
        *,
        portable: bool = False,
        persistent_available: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Google 圖片搜尋設定")
        self.setModal(True)
        self.portable = portable

        self.api_key = QLineEdit(initial.api_key if initial else "", self)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Google Custom Search API Key")
        self.search_engine_id = QLineEdit(
            initial.search_engine_id if initial else "", self
        )
        self.search_engine_id.setPlaceholderText("Programmable Search Engine ID")
        self.reveal = QCheckBox("顯示 API Key", self)
        self.reveal.toggled.connect(
            lambda checked: self.api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )

        form = QFormLayout()
        form.addRow("API Key", self.api_key)
        form.addRow("Search Engine ID", self.search_engine_id)
        form.addRow("", self.reveal)

        warning = QLabel(
            "只會傳送書名、作者、ISBN 與搜尋關鍵字；不會上傳 EPUB、DOCX 或 PDF。",
            self,
        )
        warning.setWordWrap(True)

        self.save_button = QPushButton(
            "儲存到可攜資料夾" if portable else "儲存到 Windows",
            self,
        )
        self.save_button.setEnabled(persistent_available)
        self.once_button = QPushButton("僅本次使用", self)
        self.clear_button = QPushButton("清除已儲存", self)
        self.cancel_button = QPushButton("取消", self)

        buttons = QHBoxLayout()
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.once_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(warning)
        layout.addLayout(form)
        layout.addLayout(buttons)

        self.save_button.clicked.connect(self._save)
        self.once_button.clicked.connect(self._use_once)
        self.clear_button.clicked.connect(self._clear)
        self.cancel_button.clicked.connect(self.reject)

    def _value(self) -> ProviderCredential | None:
        value = ProviderCredential(
            self.api_key.text().strip(),
            self.search_engine_id.text().strip(),
        )
        if not value.complete:
            QMessageBox.warning(
                self,
                "資料不完整",
                "API Key 與 Search Engine ID 都必須填寫。",
            )
            return None
        return value

    def _save(self) -> None:
        value = self._value()
        if value is None:
            return
        if self.portable:
            answer = QMessageBox.warning(
                self,
                "可攜模式憑證風險",
                "API Key 將以可讀取的 JSON 儲存在可攜資料夾。取得該資料夾的人可能讀取憑證。仍要儲存嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            mode = "portable"
        else:
            mode = "system"
        self.credential_chosen.emit(value, mode)
        self.accept()

    def _use_once(self) -> None:
        value = self._value()
        if value is not None:
            self.credential_chosen.emit(value, "session")
            self.accept()

    def _clear(self) -> None:
        self.clear_requested.emit()
        self.api_key.clear()
        self.search_engine_id.clear()
