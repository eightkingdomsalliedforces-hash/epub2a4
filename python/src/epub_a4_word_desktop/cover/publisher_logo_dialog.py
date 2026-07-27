from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.publisher_directory import PublisherProfile
from epub_a4_word.cover.search.logo_models import (
    LogoCandidate,
    LogoSearchPage,
    LogoSourceCategory,
)
from epub_a4_word.cover.search.publisher_logo import PublisherLogoSearch

_SOURCE_LABELS = {
    LogoSourceCategory.OFFICIAL: "官方來源",
    LogoSourceCategory.OFFICIAL_SOCIAL: "官方社群",
    LogoSourceCategory.WIKIMEDIA: "Wikimedia Commons",
    LogoSourceCategory.WIKIPEDIA: "Wikipedia",
    LogoSourceCategory.OTHER: "公開來源",
    LogoSourceCategory.MANUAL: "手動圖片",
}


class _WorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class _SearchWorker(QRunnable):
    def __init__(self, service, query: str, profile: PublisherProfile, token: str | None) -> None:
        super().__init__()
        self.service = service
        self.query = query
        self.profile = profile
        self.token = token
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            page = self.service.search(
                self.query,
                profile=self.profile,
                page_token=self.token,
                limit=20,
            )
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.completed.emit(page)


class PublisherLogoDialog(QDialog):
    manual_file_requested = Signal()
    no_logo_requested = Signal()

    def __init__(
        self,
        *,
        search_service=None,
        auto_start: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("選擇出版社 Logo")
        self.resize(780, 560)
        self.search_service = search_service or PublisherLogoSearch()
        self.auto_start = bool(auto_start)
        self.pool = QThreadPool.globalInstance()
        self.network = QNetworkAccessManager(self)
        self._thumbnail_replies: dict[QNetworkReply, QListWidgetItem] = {}
        self._workers: set[_SearchWorker] = set()
        self._query = ""
        self._profile: PublisherProfile | None = None
        self._next_page_token: str | None = None

        self.heading = QLabel("", self)
        self.heading.setWordWrap(True)
        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        self.results = QListWidget(self)
        self.results.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.results.currentItemChanged.connect(self._selection_changed)

        self.preview = QLabel("", self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(120)
        self.preview.setMaximumHeight(180)
        self.details = QLabel("請從候選清單選擇一張 Logo。", self)
        self.details.setWordWrap(True)
        self.open_source_button = QPushButton("開啟來源頁", self)
        self.open_source_button.setEnabled(False)
        self.open_source_button.clicked.connect(self._open_source)

        self.load_more_button = QPushButton("載入更多", self)
        self.load_more_button.setEnabled(False)
        self.load_more_button.clicked.connect(lambda _checked=False: self.load_more())
        self.manual_button = QPushButton("手動選擇圖片", self)
        self.manual_button.clicked.connect(self._manual)
        self.no_logo_button = QPushButton("不使用 Logo", self)
        self.no_logo_button.clicked.connect(self._no_logo)

        actions = QHBoxLayout()
        actions.addWidget(self.load_more_button)
        actions.addWidget(self.manual_button)
        actions.addWidget(self.no_logo_button)
        actions.addWidget(self.open_source_button)
        actions.addStretch(1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.choose_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.choose_button.setText("使用所選 Logo")
        self.choose_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.heading)
        layout.addWidget(self.status)
        layout.addWidget(self.results, 1)
        layout.addWidget(self.preview)
        layout.addWidget(self.details)
        layout.addLayout(actions)
        layout.addWidget(self.buttons)

    def start_search(
        self,
        query: str,
        profile: PublisherProfile,
        *,
        synchronous: bool = False,
    ) -> None:
        self._query = str(query).strip()
        self._profile = profile
        self._next_page_token = None
        self.results.clear()
        self.heading.setText(f"出版社：{profile.display_name or self._query}")
        self._request_page(None, append=False, synchronous=synchronous)

    def load_more(self, *, synchronous: bool = False) -> None:
        if not self._next_page_token:
            return
        self._request_page(self._next_page_token, append=True, synchronous=synchronous)

    def _request_page(self, token: str | None, *, append: bool, synchronous: bool) -> None:
        if self._profile is None:
            return
        self.status.setText("正在搜尋 Logo 候選…")
        self.load_more_button.setEnabled(False)
        if synchronous:
            try:
                page = self.search_service.search(
                    self._query,
                    profile=self._profile,
                    page_token=token,
                    limit=20,
                )
            except Exception as exc:
                self._failed(str(exc))
            else:
                self.set_page(page, append=append)
            return
        worker = _SearchWorker(self.search_service, self._query, self._profile, token)
        self._workers.add(worker)
        worker.signals.completed.connect(
            lambda page, current=worker, add=append: self._worker_completed(current, page, add)
        )
        worker.signals.failed.connect(
            lambda message, current=worker: self._worker_failed(current, message)
        )
        self.pool.start(worker)

    @Slot(object)
    def set_page(self, page: LogoSearchPage, *, append: bool = False) -> None:
        if not append:
            self.results.clear()
        existing = {
            item.data(Qt.ItemDataRole.UserRole).dedupe_key
            for index in range(self.results.count())
            if isinstance(
                (item := self.results.item(index)).data(Qt.ItemDataRole.UserRole),
                LogoCandidate,
            )
        }
        for candidate in page.candidates:
            if candidate.dedupe_key in existing:
                continue
            label = _SOURCE_LABELS[candidate.source_category]
            if candidate.official_source and candidate.source_category is not LogoSourceCategory.OFFICIAL:
                label += " · 官方確認"
            dimensions = (
                f" · {candidate.width_px}×{candidate.height_px}"
                if candidate.width_px and candidate.height_px
                else ""
            )
            media = f" · {candidate.media_type}" if candidate.media_type else ""
            licence = candidate.license_text or "授權資訊未知"
            item = QListWidgetItem(
                f"{candidate.title}\n{label}{dimensions}{media}\n{licence}"
            )
            item.setData(Qt.ItemDataRole.UserRole, candidate)
            item.setToolTip(candidate.source_page)
            self.results.addItem(item)
            self._request_thumbnail(item, candidate.preview_url)
            existing.add(candidate.dedupe_key)
        self._next_page_token = page.next_page_token
        self.load_more_button.setEnabled(bool(self._next_page_token))
        warnings = "；".join(page.warnings)
        count = self.results.count()
        self.status.setText(
            (f"找到 {count} 張候選。" if count else "沒有找到 Logo 候選。")
            + (f" {warnings}" if warnings else "")
        )
        self.results.clearSelection()
        self.results.setCurrentRow(-1)
        self._selection_changed(None, None)

    def selected_candidate(self) -> LogoCandidate | None:
        item = self.results.currentItem()
        candidate = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return candidate if isinstance(candidate, LogoCandidate) else None

    def _selection_changed(self, current, _previous) -> None:
        candidate = self.selected_candidate()
        self.choose_button.setEnabled(candidate is not None)
        self.open_source_button.setEnabled(candidate is not None)
        if candidate is None:
            self.preview.clear()
            self.details.setText("請從候選清單選擇一張 Logo。")
            return
        source = _SOURCE_LABELS[candidate.source_category]
        licence = candidate.license_text or "授權資訊未知"
        transparency = {
            True: "透明背景",
            False: "不透明背景",
            None: "透明背景未知",
        }[candidate.transparent_background]
        self.details.setText(
            f"{candidate.title}\n來源：{source} · {candidate.source_domain or '未知'}\n"
            f"{transparency} · {licence}\n{candidate.source_page}"
        )
        item = self.results.currentItem()
        if item is not None and not item.icon().isNull():
            self.preview.setPixmap(item.icon().pixmap(520, 160))


    def _request_thumbnail(self, item: QListWidgetItem, url: str) -> None:
        if not url or QUrl(url).scheme().casefold() not in {"http", "https"}:
            return
        reply = self.network.get(QNetworkRequest(QUrl(url)))
        self._thumbnail_replies[reply] = item
        reply.downloadProgress.connect(
            lambda received, _total, current=reply: current.abort()
            if received > 2 * 1024 * 1024
            else None
        )
        reply.finished.connect(lambda current=reply: self._thumbnail_finished(current))

    def _thumbnail_finished(self, reply: QNetworkReply) -> None:
        item = self._thumbnail_replies.pop(reply, None)
        try:
            if item is None or reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = bytes(reply.readAll())
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                return
            item.setIcon(QIcon(pixmap))
            if item is self.results.currentItem():
                self.preview.setPixmap(
                    pixmap.scaled(
                        520,
                        160,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        finally:
            reply.deleteLater()

    def _worker_completed(self, worker: _SearchWorker, page: LogoSearchPage, append: bool) -> None:
        self._workers.discard(worker)
        self.set_page(page, append=append)

    def _worker_failed(self, worker: _SearchWorker, message: str) -> None:
        self._workers.discard(worker)
        self._failed(message)

    def _failed(self, message: str) -> None:
        self.status.setText(f"搜尋失敗：{message}")
        self.load_more_button.setEnabled(bool(self._next_page_token))

    def _open_source(self) -> None:
        candidate = self.selected_candidate()
        if candidate is None:
            return
        url = QUrl(candidate.source_page)
        if url.scheme().casefold() in {"http", "https"}:
            QDesktopServices.openUrl(url)
        else:
            QMessageBox.warning(self, "無法開啟", "來源網址不是有效的 HTTP／HTTPS 網址。")

    def _manual(self) -> None:
        self.manual_file_requested.emit()
        self.reject()

    def _no_logo(self) -> None:
        self.no_logo_requested.emit()
        self.reject()
