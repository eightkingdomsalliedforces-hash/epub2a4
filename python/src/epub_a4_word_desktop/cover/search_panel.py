from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.search.models import CandidateCategory, SearchCandidate

from .credential_dialog import CredentialDialog
from .search_controller import SearchController

_CATEGORY_LABELS = {
    CandidateCategory.FRONT: "正面",
    CandidateCategory.BACK: "背面",
    CandidateCategory.SPINE: "書脊",
    CandidateCategory.FULL_SPREAD: "完整書衣",
    CandidateCategory.REFERENCE_PHOTO: "實拍參考",
    CandidateCategory.UNKNOWN: "無法判定",
}


class CandidateCard(QFrame):
    selected = Signal(object, str)

    def __init__(
        self,
        candidate: SearchCandidate,
        network: QNetworkAccessManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.network = network
        self._reply = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(185)
        self.setMaximumWidth(230)

        self.preview = QLabel("載入縮圖…", self)
        self.preview.setFixedSize(170, 235)
        self.preview.setScaledContents(False)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background: palette(midlight); border: 1px solid palette(mid);")

        self.category = QComboBox(self)
        for value, label in _CATEGORY_LABELS.items():
            self.category.addItem(label, value.value)
        index = self.category.findData(candidate.proposed_category.value)
        self.category.setCurrentIndex(max(0, index))

        title = candidate.title.strip() or urlsplit(candidate.source_page).netloc
        self.title_label = QLabel(title or "未命名圖片", self)
        self.title_label.setWordWrap(True)
        provider = QLabel(f"來源：{candidate.provider}", self)
        resolution = (
            f"{candidate.width_px} × {candidate.height_px}"
            if candidate.width_px and candidate.height_px
            else "解析度未知"
        )
        resolution_label = QLabel(resolution, self)
        rights = QLabel(
            candidate.rights.strip()
            or "授權狀態未確認；使用者需自行確認使用權",
            self,
        )
        rights.setWordWrap(True)
        rights.setStyleSheet("font-size: 10px;")

        source_button = QPushButton("查看來源", self)
        choose_button = QPushButton("選擇此圖", self)
        source_button.clicked.connect(self._open_source)
        choose_button.clicked.connect(self._choose)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.category)
        layout.addWidget(self.title_label)
        layout.addWidget(provider)
        layout.addWidget(resolution_label)
        layout.addWidget(rights)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(source_button)
        row.addWidget(choose_button)
        layout.addLayout(row)
        self._load_preview()

    def _load_preview(self) -> None:
        url = QUrl(self.candidate.preview_url)
        if not url.isValid() or url.scheme().lower() != "https":
            self.preview.setText("無法載入縮圖")
            return
        self._reply = self.network.get(QNetworkRequest(url))
        self._reply.finished.connect(self._preview_finished)

    def _preview_finished(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        data = bytes(reply.readAll())
        reply.deleteLater()
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            self.preview.setText("縮圖載入失敗")
            return
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _open_source(self) -> None:
        url = QUrl(self.candidate.source_page)
        if url.isValid() and url.scheme().lower() == "https":
            QDesktopServices.openUrl(url)
        else:
            QMessageBox.warning(self, "無法開啟", "來源網址不是有效的 HTTPS 網址。")

    def _choose(self) -> None:
        self.selected.emit(self.candidate, str(self.category.currentData()))


class CoverSearchPanel(QWidget):
    apply_requested = Signal(str, object)

    def __init__(
        self,
        controller: SearchController,
        *,
        portable: bool = False,
        persistent_available: bool = True,
        auto_search: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.portable = portable
        self.persistent_available = persistent_available
        self.auto_search = bool(auto_search)
        self.metadata: dict[str, object] = {}
        self.project_fingerprint = ""
        self.candidates: dict[tuple[str, str], SearchCandidate] = {}
        self.selected: dict[str, SearchCandidate] = {}
        self.cards: list[CandidateCard] = []
        self._columns = 0
        self.network = QNetworkAccessManager(self)

        self.metadata_label = QLabel("建立封面專案後會自動搜尋。", self)
        self.metadata_label.setWordWrap(True)
        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        self.configure_credentials_button = QPushButton("設定圖片搜尋", self)
        self.search_public_button = QPushButton("重新搜尋公開書庫", self)
        self.search_general_button = QPushButton("搜尋正面／背面／書脊／完整書衣", self)
        self.search_general_button.setEnabled(False)

        actions = QHBoxLayout()
        actions.addWidget(self.search_public_button)
        actions.addWidget(self.search_general_button)
        actions.addWidget(self.configure_credentials_button)
        actions.addStretch(1)

        self.grid_host = QWidget(self)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(10)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_host)

        selection_box = QGroupBox("已選素材", self)
        self.selection_label = QLabel("尚未選擇圖片。", selection_box)
        self.selection_label.setWordWrap(True)
        self.apply_segmented_button = QPushButton("分區編輯", selection_box)
        self.apply_composite_button = QPushButton("合成完整書衣", selection_box)
        self.apply_segmented_button.setEnabled(False)
        self.apply_composite_button.setEnabled(False)
        selection_layout = QVBoxLayout(selection_box)
        selection_layout.addWidget(self.selection_label)
        selection_actions = QHBoxLayout()
        selection_actions.addWidget(self.apply_segmented_button)
        selection_actions.addWidget(self.apply_composite_button)
        selection_actions.addStretch(1)
        selection_layout.addLayout(selection_actions)

        layout = QVBoxLayout(self)
        layout.addWidget(self.metadata_label)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(selection_box)

        self.search_public_button.clicked.connect(self._search_public)
        self.search_general_button.clicked.connect(self._search_general)
        self.configure_credentials_button.clicked.connect(self._configure_credentials)
        self.apply_segmented_button.clicked.connect(
            lambda: self.apply_requested.emit("segmented", dict(self.selected))
        )
        self.apply_composite_button.clicked.connect(
            lambda: self.apply_requested.emit("composite", dict(self.selected))
        )
        self.controller.results_ready.connect(self._results_ready)
        self.controller.search_failed.connect(self._search_failed)
        self.controller.credential_required.connect(self._credential_missing)
        self._update_credential_state()

    def bind_project(self, project_json: str) -> None:
        project = loads_project(project_json)
        metadata = asdict(project.metadata)
        fingerprint = "|".join(
            (
                project.source_file,
                str(metadata.get("isbn", "")),
                str(metadata.get("title", "")),
                str(metadata.get("author", "")),
            )
        )
        self.metadata = metadata
        self.metadata["source_file"] = project.source_file
        self.metadata_label.setText(
            f"書名：{project.metadata.title or '未取得'}　作者：{project.metadata.author or '未取得'}　ISBN：{project.metadata.isbn or '未取得'}"
        )
        if fingerprint == self.project_fingerprint:
            return
        self.project_fingerprint = fingerprint
        self.candidates.clear()
        self.selected.clear()
        self._rebuild_cards()
        self._update_selection_summary()
        if not self.auto_search:
            self.status_label.setText("封面搜尋已準備完成；按搜尋按鈕後才會連線。")
            self._update_credential_state()
            return
        self._search_public()
        credential = self.controller.stored_credential()
        if credential is not None and credential.complete:
            self.controller.search_general(self.metadata, credential)
            self.status_label.setText("正在背景搜尋公開書庫與完整封面素材…")
        else:
            self.status_label.setText("正在搜尋公開書庫；設定圖片搜尋後可找背面、書脊與完整書衣。")
        self._update_credential_state()

    def _search_public(self) -> None:
        if not self.metadata:
            return
        if not any(str(self.metadata.get(key, "")).strip() for key in ("isbn", "title")):
            self.status_label.setText("缺少 ISBN 與書名，無法自動搜尋公開書庫。")
            return
        self.controller.search_public(self.metadata)
        self.status_label.setText("正在搜尋 Google Books 與 Open Library…")

    def _search_general(self) -> None:
        if self.metadata:
            self.controller.search_general(self.metadata)
            self.status_label.setText("正在搜尋正面、背面、書脊、完整書衣與實拍參考圖…")

    def _credential_missing(self) -> None:
        self.configure_credentials_button.show()
        self.search_general_button.setEnabled(False)
        self.status_label.setText("尚未設定 Google 圖片搜尋；公開書庫搜尋仍可使用。")

    def _update_credential_state(self) -> None:
        credential = self.controller.stored_credential()
        ready = credential is not None and credential.complete
        self.search_general_button.setEnabled(ready and bool(self.metadata))
        self.configure_credentials_button.setText(
            "修改圖片搜尋設定" if ready else "設定圖片搜尋"
        )

    def _configure_credentials(self) -> None:
        dialog = CredentialDialog(
            self.controller.stored_credential(),
            portable=self.portable,
            persistent_available=self.persistent_available,
            parent=self,
        )
        dialog.credential_chosen.connect(self._credential_chosen)
        dialog.clear_requested.connect(self._clear_credentials)
        dialog.exec()

    def _credential_chosen(self, value, mode: str) -> None:
        try:
            if mode == "session":
                self.controller.save_session_credential(value)
            elif mode == "portable":
                self.controller.save_persistent_credential(
                    value, confirmed_plaintext=True
                )
            else:
                self.controller.save_persistent_credential(value)
        except Exception as exc:
            QMessageBox.warning(self, "無法儲存憑證", str(exc))
            self.controller.save_session_credential(value)
        self._update_credential_state()
        if self.metadata:
            self.controller.search_general(self.metadata, value)

    def _clear_credentials(self) -> None:
        self.controller.clear_credentials()
        self._update_credential_state()

    def _results_ready(self, mode: str, response) -> None:
        for candidate in response.candidates:
            self.candidates[(candidate.query_kind.value, candidate.image_url)] = candidate
        self._rebuild_cards()
        warning = "；".join(response.warnings)
        if warning:
            self.status_label.setText(f"{mode} 搜尋完成，但部分來源失敗：{warning}")
        elif response.candidates:
            self.status_label.setText(f"已取得 {len(self.candidates)} 張候選圖片。")
        else:
            self.status_label.setText("找不到候選封面；本機與內嵌圖片仍可正常使用。")

    def _search_failed(self, mode: str, message: str) -> None:
        self.status_label.setText(f"{mode} 搜尋失敗：{message}；已取得的候選不會被清除。")

    def _candidate_selected(self, candidate: SearchCandidate, category: str) -> None:
        selected_category = CandidateCategory(category)
        if selected_category in {CandidateCategory.UNKNOWN, CandidateCategory.REFERENCE_PHOTO}:
            QMessageBox.information(
                self,
                "請指定用途",
                "請先把分類改成正面、背面、書脊或完整書衣，再選擇。",
            )
            return
        self.selected[selected_category.value] = candidate
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        if not self.selected:
            self.selection_label.setText("尚未選擇圖片。")
        else:
            labels = [
                f"{_CATEGORY_LABELS[CandidateCategory(key)]}：{value.title or urlsplit(value.source_page).netloc}"
                for key, value in self.selected.items()
            ]
            self.selection_label.setText("\n".join(labels))
        segmented = any(key in self.selected for key in ("front", "back", "spine"))
        composite = segmented or "full_spread" in self.selected
        self.apply_segmented_button.setEnabled(segmented)
        self.apply_composite_button.setEnabled(composite)

    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.cards.clear()

    def _rebuild_cards(self) -> None:
        self._clear_grid()
        ordered = sorted(
            self.candidates.values(),
            key=lambda item: (
                list(CandidateCategory).index(item.proposed_category),
                -item.classification_confidence,
                -(item.width_px or 0) * (item.height_px or 0),
            ),
        )
        columns = max(1, self.scroll.viewport().width() // 235)
        self._columns = columns
        for index, candidate in enumerate(ordered):
            card = CandidateCard(candidate, self.network, self.grid_host)
            card.selected.connect(self._candidate_selected)
            self.cards.append(card)
            self.grid.addWidget(card, index // columns, index % columns)
        self.grid.setRowStretch((len(ordered) + columns - 1) // columns, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        columns = max(1, self.scroll.viewport().width() // 235)
        if self.cards and columns != self._columns:
            self._rebuild_cards()
