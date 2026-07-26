from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import time
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.search.models import (
    CandidateCategory,
    ResolvedAlias,
    SearchCandidate,
    alias_key,
)
from epub_a4_word.cover.search.pipeline import ProviderSelection

from .alias_decision_row import AliasDecisionRow
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
        for value, label in (
            (CandidateCategory.FRONT, "正面封面"),
            (CandidateCategory.BACK, "手動當作封底（來源未保證）"),
        ):
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
        isbn_lines = [
            f"ISBN-{len(value)} {value}"
            for value in candidate.isbns
        ]
        self.isbn_label = QLabel("\n".join(isbn_lines), self)
        self.isbn_label.setWordWrap(True)
        self.isbn_label.setVisible(bool(isbn_lines))
        rights = QLabel(
            candidate.rights.strip()
            or "授權狀態未確認；使用者需自行確認使用權",
            self,
        )
        rights.setWordWrap(True)
        rights.setStyleSheet("font-size: 10px;")

        source_button = QPushButton("查看來源", self)
        self.choose_button = QPushButton("加入選取", self)
        source_button.clicked.connect(self._open_source)
        self.choose_button.clicked.connect(self._choose)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.category)
        layout.addWidget(self.title_label)
        layout.addWidget(provider)
        layout.addWidget(resolution_label)
        layout.addWidget(self.isbn_label)
        layout.addWidget(rights)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(source_button)
        row.addWidget(self.choose_button)
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

    def set_selected_category(self, category: CandidateCategory | None) -> None:
        if category is None:
            self.choose_button.setText("加入選取")
            self.setStyleSheet("")
            return
        self.choose_button.setText(f"已選為{_CATEGORY_LABELS[category]} ✓")
        self.setStyleSheet("QFrame { border: 2px solid palette(highlight); }")


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
        self.accepted_aliases: dict[str, ResolvedAlias] = {}
        self.ignored_alias_keys: set[str] = set()
        self.pending_aliases: dict[str, ResolvedAlias] = {}
        self.alias_rows: list[AliasDecisionRow] = []
        self.cards: list[CandidateCard] = []
        self._columns = 0
        self._search_started_at = 0.0
        self.network = QNetworkAccessManager(self)

        self.metadata_label = QLabel("建立封面專案後會自動搜尋。", self)
        self.metadata_label.setWordWrap(True)
        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        self.status_label.setMaximumHeight(64)
        self.resolution_label = QLabel("", self)
        self.resolution_label.setWordWrap(True)
        self.resolution_label.setMaximumHeight(64)
        self.alias_box = QGroupBox("需要確認的書名別名", self)
        self.alias_box.setVisible(False)
        alias_box_layout = QVBoxLayout(self.alias_box)
        alias_box_layout.addWidget(QLabel("確認後才會使用該名稱重新搜尋。", self.alias_box))
        self.alias_rows_host = QWidget(self.alias_box)
        self.alias_rows_layout = QVBoxLayout(self.alias_rows_host)
        self.alias_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.alias_scroll = QScrollArea(self.alias_box)
        self.alias_scroll.setWidgetResizable(True)
        self.alias_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.alias_scroll.setMaximumHeight(150)
        self.alias_scroll.setWidget(self.alias_rows_host)
        alias_box_layout.addWidget(self.alias_scroll)

        self.google_books_checkbox = QCheckBox("Google Books", self)
        self.open_library_checkbox = QCheckBox("Open Library", self)
        self.gutendex_checkbox = QCheckBox("Project Gutenberg", self)
        for checkbox in (
            self.google_books_checkbox,
            self.open_library_checkbox,
            self.gutendex_checkbox,
        ):
            checkbox.setChecked(True)
        self.manual_alias_edit = QLineEdit(self)
        self.manual_alias_edit.setPlaceholderText(
            "原文書名／英文名／其他正式別名（選填）"
        )
        self.search_button = QPushButton("搜尋封面", self)
        self.search_button.setEnabled(False)
        self.search_more_button = QPushButton("搜尋更多", self)
        self.search_more_button.setEnabled(False)
        self.search_public_button = self.search_button
        self.configure_credentials_button = QPushButton("Google Books API 設定", self)
        self.clear_alias_cache_button = QPushButton("清除別名快取", self)

        actions = QHBoxLayout()
        actions.addWidget(self.google_books_checkbox)
        actions.addWidget(self.open_library_checkbox)
        actions.addWidget(self.gutendex_checkbox)
        actions.addWidget(self.search_button)
        actions.addWidget(self.search_more_button)
        actions.addWidget(self.configure_credentials_button)
        actions.addWidget(self.clear_alias_cache_button)
        actions.addStretch(1)

        self.grid_host = QWidget(self)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(10)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_host)

        self.back_cover_help = QLabel(
            "公開書庫通常只提供正面。封底會優先使用 EPUB 內建封底；沒有時請在左側「素材」選擇封底並加入本機圖片。仍可明確保留空白，匯出前會再次確認。",
            self,
        )
        self.back_cover_help.setWordWrap(True)
        self.back_cover_help.setStyleSheet("font-size: 11px;")

        self.selection_box = QGroupBox("已選素材與套用", self)
        self.selection_label = QLabel("尚未選擇圖片。", self.selection_box)
        self.selection_label.setWordWrap(True)
        self.apply_segmented_button = QPushButton("套用所選圖片到封面", self.selection_box)
        self.apply_composite_button = QPushButton("將所選圖片合成完整書衣", self.selection_box)
        self.apply_segmented_button.setEnabled(False)
        self.apply_composite_button.setEnabled(False)
        selection_layout = QVBoxLayout(self.selection_box)
        selection_layout.addWidget(self.selection_label)
        selection_actions = QHBoxLayout()
        selection_actions.addWidget(self.apply_segmented_button)
        selection_actions.addWidget(self.apply_composite_button)
        selection_actions.addStretch(1)
        selection_layout.addLayout(selection_actions)

        layout = QVBoxLayout(self)
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.manual_alias_edit)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)
        layout.addWidget(self.resolution_label)
        layout.addWidget(self.alias_box)
        layout.addWidget(self.back_cover_help)
        layout.addWidget(self.selection_box)
        layout.addWidget(self.scroll, 1)

        self.search_button.clicked.connect(self._search)
        self.search_more_button.clicked.connect(lambda _checked=False: self._search(exhaustive=True))
        self.configure_credentials_button.clicked.connect(self._configure_credentials)
        self.clear_alias_cache_button.clicked.connect(self._clear_alias_cache)
        for checkbox in (
            self.google_books_checkbox,
            self.open_library_checkbox,
            self.gutendex_checkbox,
        ):
            checkbox.toggled.connect(self._update_search_enabled)
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
        self._update_search_enabled()

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
        has_back_image = any(
            element.kind.value == "image"
            and element.region.value == "back"
            and element.opacity > 0
            for element in project.elements
        )
        has_back_candidate = any(
            str(asset.get("role", "")) == "back_cover_candidate"
            for asset in project.metadata.embedded_images
        )
        if has_back_image:
            self.back_cover_help.setText(
                "目前封底：已使用 EPUB 內建封底或已加入的封底圖片。公開書庫結果仍只當作正面候選。"
            )
        elif has_back_candidate:
            self.back_cover_help.setText(
                "EPUB 找到一張可能的封底，但可信度不足，沒有自動套用。請在左側「素材」選擇標示為「可能封底（需確認）」的圖片，區域選「封底」後加入。"
            )
        else:
            self.back_cover_help.setText(
                "公開書庫通常只提供正面。封底會優先使用 EPUB 內建封底；沒有時請在左側「素材」選擇封底並加入本機圖片。仍可明確保留空白，匯出前會再次確認。"
            )
        if fingerprint == self.project_fingerprint:
            return
        self.project_fingerprint = fingerprint
        self.candidates.clear()
        self.selected.clear()
        self.accepted_aliases.clear()
        self.ignored_alias_keys.clear()
        self.pending_aliases.clear()
        self._rebuild_alias_rows(())
        self._rebuild_cards()
        self._update_selection_summary()
        self._update_search_enabled()
        if not self.auto_search:
            self.status_label.setText("封面搜尋已準備完成；按搜尋按鈕後才會連線。")
            self._update_credential_state()
            return
        self._search()
        self._update_credential_state()

    def _provider_selection(self) -> ProviderSelection:
        return ProviderSelection(
            google_books=self.google_books_checkbox.isChecked(),
            open_library=self.open_library_checkbox.isChecked(),
            gutendex=self.gutendex_checkbox.isChecked(),
        )

    def _update_search_enabled(self, _checked: object = None) -> None:
        selection = self._provider_selection()
        ready = bool(self.metadata) and selection.any_enabled
        self.search_button.setEnabled(ready)
        self.search_more_button.setEnabled(ready and bool(self.candidates))
        if self.metadata and not selection.any_enabled:
            self.status_label.setText("至少啟用一個封面搜尋來源。")

    def _search(self, _checked: object = None, *, exhaustive: bool = False) -> None:
        if not self.metadata:
            return
        selection = self._provider_selection()
        if not selection.any_enabled:
            self.status_label.setText("至少啟用一個封面搜尋來源。")
            return
        if not any(str(self.metadata.get(key, "")).strip() for key in ("isbn", "title")):
            self.status_label.setText("缺少 ISBN 與書名，無法自動搜尋公開書庫。")
            return
        self.controller.search_public(
            self.metadata,
            selection,
            self.manual_alias_edit.text().strip(),
            tuple(self.accepted_aliases.values()),
            frozenset(self.ignored_alias_keys),
            exhaustive,
        )
        self._search_started_at = time.monotonic()
        self.search_button.setEnabled(False)
        self.search_more_button.setEnabled(False)
        self.search_button.setText("搜尋中…")
        enabled = []
        if selection.google_books:
            enabled.append("Google Books")
        if selection.open_library:
            enabled.append("Open Library")
        if selection.gutendex:
            enabled.append("Project Gutenberg")
        self.status_label.setText("正在搜尋：" + "、".join(enabled) + "…")

    def _search_public(self) -> None:
        self._search()

    def _credential_missing(self) -> None:
        self.configure_credentials_button.show()
        self.status_label.setText(
            "尚未設定 Google Books API Key；Open Library 與 Project Gutenberg 仍可使用。"
        )
        self._update_search_enabled()

    def _update_credential_state(self) -> None:
        credential = self.controller.stored_credential()
        ready = credential is not None and credential.complete
        self.configure_credentials_button.setText(
            "修改 Google Books API 設定" if ready else "Google Books API 設定"
        )
        self._update_search_enabled()

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
            self._search()

    def _clear_credentials(self) -> None:
        self.controller.clear_credentials()
        self._update_credential_state()

    def _clear_alias_cache(self) -> None:
        self.controller.clear_alias_cache()
        self.resolution_label.setText("已清除本機書名別名快取。")

    def _results_ready(self, mode: str, response) -> None:
        for candidate in response.candidates:
            self.candidates[(candidate.query_kind.value, candidate.image_url)] = candidate
        self._rebuild_cards()
        elapsed = max(0.0, time.monotonic() - self._search_started_at) if self._search_started_at else 0.0
        self.search_button.setText("搜尋封面")
        self._update_search_enabled()
        self.search_more_button.setEnabled(
            bool(self.metadata) and self._provider_selection().any_enabled
        )
        warning = "；".join(response.warnings)
        if warning:
            self.status_label.setText(f"搜尋完成（{elapsed:.1f} 秒），但部分來源失敗：{warning}")
        elif response.candidates:
            self.status_label.setText(f"已取得 {len(self.candidates)} 張候選圖片（{elapsed:.1f} 秒）。")
        else:
            self.status_label.setText(f"找不到候選封面（{elapsed:.1f} 秒）；可按「搜尋更多」擴大查詢。")
        aliases = getattr(response, "resolved_aliases", ())
        pending = getattr(response, "pending_aliases", ())
        self._rebuild_alias_rows(pending)
        isbns = getattr(response, "resolved_isbns", ())
        confirmed_text = "、".join(
            item.value
            for item in aliases
            if item.confidence != "medium" or alias_key(item) in self.accepted_aliases
        )
        details = []
        if confirmed_text:
            details.append("可使用名稱：" + confirmed_text)
        if isbns:
            details.append("解析 ISBN：" + "、".join(isbns))
        self.resolution_label.setText("；".join(details))

    def _clear_alias_rows(self) -> None:
        while self.alias_rows_layout.count():
            item = self.alias_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.alias_rows.clear()

    def _rebuild_alias_rows(self, aliases) -> None:
        self._clear_alias_rows()
        self.pending_aliases = {
            alias_key(alias): alias
            for alias in aliases
            if alias_key(alias) not in self.ignored_alias_keys
            and alias_key(alias) not in self.accepted_aliases
        }
        for alias in self.pending_aliases.values():
            row = AliasDecisionRow(alias, self.alias_box)
            row.accepted.connect(self._accept_alias)
            row.ignored.connect(self._ignore_alias)
            self.alias_rows.append(row)
            self.alias_rows_layout.addWidget(row)
        self.alias_box.setVisible(bool(self.alias_rows))

    def _accept_alias(self, alias: ResolvedAlias) -> None:
        key = alias_key(alias)
        self.accepted_aliases[key] = alias
        self.ignored_alias_keys.discard(key)
        self.pending_aliases.pop(key, None)
        self._rebuild_alias_rows(tuple(self.pending_aliases.values()))
        self._search()

    def _ignore_alias(self, key: str) -> None:
        normalized = str(key).casefold().strip()
        self.accepted_aliases.pop(normalized, None)
        self.ignored_alias_keys.add(normalized)
        self.pending_aliases.pop(normalized, None)
        self._rebuild_alias_rows(tuple(self.pending_aliases.values()))

    def _search_failed(self, mode: str, message: str) -> None:
        self.search_button.setText("搜尋封面")
        self._update_search_enabled()
        self.search_more_button.setEnabled(
            bool(self.metadata) and self._provider_selection().any_enabled
        )
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
        for key, current in tuple(self.selected.items()):
            if current is candidate and key != selected_category.value:
                self.selected.pop(key, None)
        self.selected[selected_category.value] = candidate
        self.controller.remember_selected_alias(
            self.metadata,
            candidate,
            self.manual_alias_edit.text().strip(),
        )
        self.controller.remember_confirmed_aliases(
            self.metadata,
            tuple(self.accepted_aliases.values()),
            isbn=candidate.isbn,
        )
        self._update_selection_summary()
        for card in self.cards:
            card_category = next(
                (
                    CandidateCategory(key)
                    for key, value in self.selected.items()
                    if value is card.candidate
                ),
                None,
            )
            card.set_selected_category(card_category)
        if selected_category is CandidateCategory.BACK:
            self.status_label.setText(
                "已手動把這張公開書庫圖片指定為封底；來源通常只保證正面，請先確認圖像內容，再按「套用所選圖片到封面」。"
            )
        else:
            self.status_label.setText(
                f"已選為{_CATEGORY_LABELS[selected_category]}；按上方「套用所選圖片到封面」完成加入。"
            )

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
