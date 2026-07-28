from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from pathlib import Path
import re
from uuid import uuid4

from PySide6.QtCore import QRectF, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.composition import compose_full_spread
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.isbn import normalize_isbn, preferred_isbn, valid_isbns
from epub_a4_word.cover.publisher_directory import publisher_profile
from epub_a4_word.cover.search.logo_cache import LogoCache
from epub_a4_word.cover.search.logo_download import download_logo, import_logo_file
from epub_a4_word.cover.models import (
    CoverElement,
    ElementKind,
    ElementTransform,
    Region,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word.cover.search.models import SearchCandidate
from epub_a4_word_desktop.cover.assets_panel import AssetsPanel
from epub_a4_word_desktop.cover.canvas import CoverCanvas
from epub_a4_word_desktop.cover.composition_dialog import CompositionDialog
from epub_a4_word_desktop.cover.controller import CoverController
from epub_a4_word_desktop.cover.crop_dialog import CropDialog
from epub_a4_word_desktop.cover.export_preview_dialog import ExportPreviewDialog
from epub_a4_word_desktop.cover.export_worker import ExportWorker, export_paths
from epub_a4_word_desktop.cover.inspector import ElementInspector
from epub_a4_word_desktop.cover.layers_panel import LayersPanel
from epub_a4_word_desktop.cover.project_files import open_project_bundle, save_project_bundle
from epub_a4_word_desktop.cover.publisher_logo_dialog import PublisherLogoDialog
from epub_a4_word_desktop.cover.publisher_metadata_panel import PublisherMetadataValues
from epub_a4_word_desktop.cover.search_controller import SearchController, SharedSearchFacade
from epub_a4_word_desktop.cover.search_panel import CoverSearchPanel
from epub_a4_word_desktop.cover.setup_panel import CoverSetupPanel, CoverSetupValues
from epub_a4_word_desktop.cover.svg_logo import rasterize_svg_logo
from epub_a4_word_desktop.settings.credentials import (
    KeyringCredentialStore,
    LayeredCredentialStore,
    PortableCredentialStore,
    SessionCredentialStore,
)
from epub_a4_word_desktop.settings.paths import RuntimePaths


class TemplatePanel(QGroupBox):
    template_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("模板", parent)
        self.combo = QComboBox(self)
        for label, template_id in (
            ("極簡", "minimal"),
            ("全圖覆蓋", "full_bleed_image"),
            ("經典書籍", "classic_book"),
            ("出版社封底＋直式書脊", "publisher_back_matter"),
            ("現代直排封底＋可選書脊", "modern_vertical_back_with_spine"),
        ):
            self.combo.addItem(label, template_id)
        self.apply_button = QPushButton("套用模板", self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.combo)
        layout.addWidget(self.apply_button)
        self.apply_button.clicked.connect(
            lambda _checked=False: self.template_selected.emit(str(self.combo.currentData()))
        )


class ExportPanel(QGroupBox):
    export_requested = Signal(object, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("輸出", parent)
        self.output_dir: Path | None = None
        self.output_label = QLabel("尚未選擇輸出資料夾", self)
        self.output_label.setWordWrap(True)
        self.choose_button = QPushButton("選擇輸出資料夾", self)
        self.dpi_combo = QComboBox(self)
        self.dpi_combo.addItem("200 DPI", 200)
        self.dpi_combo.addItem("300 DPI", 300)
        self.dpi_combo.setCurrentIndex(1)
        self.export_button = QPushButton("輸出完整書衣＋A4列印檔", self)
        self.export_button.setEnabled(False)
        layout = QVBoxLayout(self)
        layout.addWidget(self.output_label)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.dpi_combo)
        layout.addWidget(self.export_button)
        self.choose_button.clicked.connect(self._choose_output_dir)
        self.export_button.clicked.connect(self._request_export)

    def set_project_loaded(self, loaded: bool) -> None:
        self.export_button.setEnabled(loaded and self.output_dir is not None)

    def set_output_dir(self, path: Path | str) -> None:
        self.output_dir = Path(path).expanduser().resolve()
        self.output_label.setText(str(self.output_dir))
        self.export_button.setEnabled(True)

    def _choose_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "選擇封面輸出資料夾")
        if selected:
            self.set_output_dir(selected)

    def _request_export(self) -> None:
        if self.output_dir is not None:
            self.export_requested.emit(self.output_dir, int(self.dpi_combo.currentData()))


class CoverPage(QWidget):
    back_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        controller: CoverController | None = None,
        runtime_paths: RuntimePaths | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cover-page")
        self.runtime_paths = runtime_paths
        working_dir = runtime_paths.data_dir if runtime_paths is not None else None
        self.controller = controller or CoverController(working_dir=working_dir, parent=self)
        self.conversion_payload: dict[str, object] | None = None
        self._export_workers: set[ExportWorker] = set()

        persistent = None
        persistent_available = False
        portable = bool(runtime_paths and runtime_paths.portable)
        if runtime_paths is not None:
            if portable:
                persistent = PortableCredentialStore(
                    runtime_paths.google_books_credentials_path
                )
                persistent_available = True
            else:
                try:
                    candidate = KeyringCredentialStore()
                    candidate.load()
                except Exception:
                    persistent = None
                else:
                    persistent = candidate
                    persistent_available = True
        credential_store = LayeredCredentialStore(
            persistent,
            SessionCredentialStore(),
        )
        search_service = SharedSearchFacade(
            alias_cache_path=(
                runtime_paths.alias_cache_path if runtime_paths is not None else None
            )
        )
        self.search_controller = SearchController(
            service=search_service,
            credential_store=credential_store,
            parent=self,
        )

        self.back_button = QPushButton("返回首頁", self)
        self.open_button = QPushButton("開啟專案", self)
        self.save_button = QPushButton("儲存專案", self)
        self.undo_button = QPushButton("復原", self)
        self.redo_button = QPushButton("重做", self)
        self.status_label = QLabel("請先選擇來源並確認正文頁數。", self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.redo_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.status_label)

        self.template_panel = TemplatePanel(self)
        self.assets_panel = AssetsPanel(self.controller, self)
        self.layers_panel = LayersPanel(self)
        self.canvas = CoverCanvas(self)
        self.inspector = ElementInspector(self)
        self.setup_panel = CoverSetupPanel(self)
        self.publisher_metadata_panel = self.setup_panel.publisher_metadata_panel
        self.publisher_metadata_panel.setEnabled(False)
        self.reset_publisher_template_button = QPushButton("重設模板版面", self)
        self.reset_publisher_template_button.setEnabled(False)
        self._publisher_update_timer = QTimer(self)
        self._publisher_update_timer.setSingleShot(True)
        self._publisher_update_timer.setInterval(300)
        self._pending_publisher_values: PublisherMetadataValues | None = None
        self._syncing_publisher_panel = False
        self.export_panel = ExportPanel(self)
        self.search_panel = CoverSearchPanel(
            self.search_controller,
            portable=portable,
            persistent_available=persistent_available,
            auto_search=runtime_paths is not None,
            parent=self,
        )

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.template_panel)
        left_layout.addWidget(self.assets_panel)
        left_layout.addWidget(self.layers_panel, 1)

        editor = QWidget(self)
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.canvas, 1)
        editor_layout.addWidget(self.canvas.zoom_controls)
        self.center_tabs = QTabWidget(self)
        self.center_tabs.addTab(editor, "封面編輯")
        self.center_tabs.addTab(self.search_panel, "搜尋封面")

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.setup_panel)
        right_layout.addWidget(self.reset_publisher_template_button)
        right_layout.addWidget(self.inspector, 1)
        right_layout.addWidget(self.export_panel)

        self.left_scroll = QScrollArea(self)
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_scroll.setWidget(left)

        self.right_scroll = QScrollArea(self)
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setMinimumWidth(330)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll.setWidget(right)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(self.left_scroll)
        self.splitter.addWidget(self.center_tabs)
        self.splitter.addWidget(self.right_scroll)
        self.splitter.setCollapsible(2, False)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([250, 760, 330])

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.splitter, 1)

        self.back_button.clicked.connect(lambda _checked=False: self.back_requested.emit())
        self.open_button.clicked.connect(self._choose_open_project)
        self.save_button.clicked.connect(self._choose_save_project)
        self.undo_button.clicked.connect(lambda _checked=False: self.controller.undo())
        self.redo_button.clicked.connect(lambda _checked=False: self.controller.redo())
        self.setup_panel.create_requested.connect(self._create_project)
        self.template_panel.template_selected.connect(self._apply_template)
        self.publisher_metadata_panel.values_changed.connect(
            self._schedule_publisher_metadata_update
        )
        self.publisher_metadata_panel.search_logo_requested.connect(
            self._search_publisher_logo
        )
        self.publisher_metadata_panel.manual_logo_requested.connect(
            self._choose_manual_publisher_logo
        )
        self.publisher_metadata_panel.clear_logo_requested.connect(
            self._clear_publisher_logo
        )
        self.publisher_metadata_panel.reextract_accent_requested.connect(
            self._reextract_accent_color
        )
        self.setup_panel.show_crop_marks_check.toggled.connect(
            self._set_crop_frame_enabled
        )
        self.reset_publisher_template_button.clicked.connect(
            self._reset_publisher_template
        )
        self._publisher_update_timer.timeout.connect(self._commit_publisher_metadata)
        self.assets_panel.image_imported.connect(self._add_image)
        self.assets_panel.add_text_requested.connect(self._add_text)
        self.assets_panel.crop_requested.connect(self._crop_asset)
        self.assets_panel.error.connect(self._show_error)
        self.export_panel.export_requested.connect(self._start_export)
        self.layers_panel.selection_changed.connect(self.canvas.select_element)
        self.layers_panel.delete_requested.connect(self.controller.remove_element)
        self.layers_panel.z_order_requested.connect(self._change_z_order)
        self.layers_panel.visibility_requested.connect(self._change_visibility)
        self.canvas.element_selected.connect(self._select_element)
        self.canvas.element_transform_requested.connect(self._commit_canvas_transform)
        self.canvas.element_patch_requested.connect(self.controller.update_element)
        self.inspector.patch_requested.connect(self.controller.update_element)
        self.controller.project_changed.connect(self._project_changed)
        self.controller.preview_ready.connect(self.canvas.set_preview)
        self.controller.error.connect(self._show_error)
        self.controller.undo_stack.canUndoChanged.connect(self.undo_button.setEnabled)
        self.controller.undo_stack.canRedoChanged.connect(self.redo_button.setEnabled)
        self.search_panel.apply_requested.connect(self._begin_search_application)
        self.search_controller.download_ready.connect(self._search_download_ready)
        self.search_controller.download_failed.connect(self._show_error)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        self.save_button.setEnabled(False)

    def save_project(self, path: Path | str) -> Path:
        if not self.controller.project_json:
            raise RuntimeError("尚未載入封面專案。")
        saved = save_project_bundle(self.controller.project_json, path)
        self.status_label.setText(f"已儲存封面專案：{saved}")
        return saved

    def open_project(self, path: Path | str) -> str:
        project_json = open_project_bundle(path)
        project = loads_project(project_json)
        self.controller.working_dir = Path(project.working_dir).resolve()
        self.controller.replace_project(project_json, clear_history=True)
        self.search_panel.bind_project(self.controller.project_json)
        self.status_label.setText(f"已開啟封面專案：{Path(path).resolve()}")
        return project_json

    def _choose_save_project(self) -> None:
        if not self.controller.project_json:
            self._show_error("尚未載入封面專案。")
            return
        project = loads_project(self.controller.project_json)
        base = project.metadata.title or Path(project.source_file).stem or "cover"
        path, _ = QFileDialog.getSaveFileName(
            self, "儲存封面專案", f"{base}.cover.json", "封面專案 (*.cover.json)"
        )
        if not path:
            return
        if not path.endswith(".cover.json"):
            path += ".cover.json"
        try:
            self.save_project(path)
        except Exception as exc:
            self._show_error(str(exc))

    def _choose_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "開啟封面專案", "", "封面專案 (*.cover.json)"
        )
        if path:
            try:
                self.open_project(path)
            except Exception as exc:
                self._show_error(str(exc))

    def open_from_conversion(self, payload: Mapping[str, object]) -> None:
        normalized = dict(payload)
        self.conversion_payload = normalized
        source_path = Path(str(normalized["source_path"]))
        page_count = int(normalized["page_count"])
        trim = normalized["trim_size_mm"]
        if not isinstance(trim, Mapping):
            raise ValueError("轉換結果的成品尺寸無效。")
        self.setup_panel.set_trim_size(float(trim["width_mm"]), float(trim["height_mm"]))
        self.setup_panel.set_source(
            source_path,
            page_count=page_count,
            estimated=False,
            confirmed=True,
        )
        self.status_label.setText("已帶入轉換後的實際頁數，請確認設定後建立封面。")

    def _create_project(self, values: CoverSetupValues) -> None:
        try:
            self.controller.load_source(
                values.source_path,
                values.settings(self.controller.working_dir),
            )
            self.controller.apply_template(values.template_id)
            self.search_panel.bind_project(self.controller.project_json)
        except Exception as exc:
            self._show_error(str(exc))

    def _schedule_publisher_metadata_update(
        self, values: PublisherMetadataValues
    ) -> None:
        if self._syncing_publisher_panel or not self.controller.project_json:
            return
        self._pending_publisher_values = values
        self._publisher_update_timer.start()

    def _commit_publisher_metadata(self) -> None:
        values = self._pending_publisher_values
        self._pending_publisher_values = None
        if values is None or not self.controller.project_json:
            return
        project = loads_project(self.controller.project_json)
        previous_publisher = project.metadata.publisher.strip()
        next_publisher = values.publisher.strip()
        publisher_changed = bool(
            previous_publisher
            and next_publisher
            and previous_publisher != next_publisher
        )
        search_replacement_logo = False
        if publisher_changed:
            search_replacement_logo = (
                QMessageBox.question(
                    self,
                    "更換出版社",
                    f"出版社已從「{previous_publisher}」改為「{next_publisher}」。是否一併搜尋替代 Logo？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )
        try:
            self.controller.update_metadata(values.as_settings())
        except Exception as exc:
            self._show_error(str(exc))
            return
        if search_replacement_logo:
            self._search_publisher_logo(next_publisher)

    def _reset_publisher_template(self, _checked: bool = False) -> None:
        if not self.controller.project_json:
            return
        try:
            values = self.publisher_metadata_panel.values()
            self.controller.update_metadata(values.as_settings(), reset_layout=True)
        except Exception as exc:
            self._show_error(str(exc))


    def _logo_cache(self) -> LogoCache:
        root = (
            self.runtime_paths.cache_dir / "publisher-logos"
            if self.runtime_paths is not None
            else self.controller.working_dir / "publisher-logo-cache"
        )
        return LogoCache(root)

    def _search_publisher_logo(self, publisher: str) -> None:
        query = str(publisher).strip()
        if not query:
            self._show_error("請先輸入出版社名稱。")
            return
        profile = publisher_profile(query)
        self.publisher_metadata_panel.publisher_id_edit.setText(profile.publisher_id)
        dialog = PublisherLogoDialog(parent=self)
        dialog.manual_file_requested.connect(self._choose_manual_publisher_logo)
        dialog.no_logo_requested.connect(self._clear_publisher_logo)
        dialog.start_search(query, profile)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        candidate = dialog.selected_candidate()
        if candidate is None:
            return
        try:
            cache = self._logo_cache()
            cached = cache.get(candidate.image_url)
            if cached is not None:
                downloaded = import_logo_file(
                    cached,
                    self.controller.working_dir / "logo-downloads",
                    svg_converter=rasterize_svg_logo,
                )
            else:
                downloaded = download_logo(
                    candidate,
                    self.controller.working_dir / "logo-downloads",
                    svg_converter=rasterize_svg_logo,
                )
                cache.put(candidate.image_url, downloaded)
            self.controller.apply_publisher_logo(downloaded, candidate)
            self.status_label.setText(
                f"已套用出版社 Logo：{candidate.title}"
            )
        except Exception as exc:
            self._show_error(str(exc))

    def _choose_manual_publisher_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇出版社 Logo",
            "",
            "Logo 圖片 (*.svg *.png *.jpg *.jpeg *.webp *.gif *.bmp *.tif *.tiff)",
        )
        if not path:
            return
        try:
            self.controller.apply_manual_publisher_logo(path)
            self.status_label.setText(f"已套用手動 Logo：{Path(path).name}")
        except Exception as exc:
            self._show_error(str(exc))

    def _clear_publisher_logo(self) -> None:
        if not self.controller.project_json:
            return
        try:
            self.controller.clear_publisher_logo()
            self.status_label.setText("已移除出版社 Logo。")
        except Exception as exc:
            self._show_error(str(exc))

    def _apply_template(self, template_id: str) -> None:
        if not self.controller.project_json:
            self.status_label.setText("請先建立封面專案。")
            return
        try:
            self.controller.apply_template(template_id)
        except Exception as exc:
            self._show_error(str(exc))

    def _set_crop_frame_enabled(self, enabled: bool) -> None:
        if not self.controller.project_json:
            return
        try:
            self.controller.set_crop_frame_enabled(enabled)
        except Exception as exc:
            self._show_error(str(exc))

    def _reextract_accent_color(self) -> None:
        if not self.controller.project_json:
            return
        try:
            self.controller.reextract_accent_color()
        except Exception as exc:
            self._show_error(str(exc))

    def _add_image(self, path: str, region: Region) -> None:
        if not self.controller.project_json:
            self.status_label.setText("請先建立封面專案。")
            return
        try:
            element_id = self.controller.add_local_image(path, region)
            self.canvas.select_element(element_id)
        except Exception as exc:
            self._show_error(str(exc))

    @staticmethod
    def _volume_number(title: str) -> int | None:
        text = str(title or "")
        for pattern in (
            r"(?:vol(?:ume)?\.?|book|#)\s*(\d+)",
            r"第\s*(\d+)\s*[卷冊集]",
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _maybe_apply_search_isbn(self, selected: Mapping[str, object]) -> None:
        candidates = tuple(
            value for value in selected.values() if isinstance(value, SearchCandidate)
        )
        if not candidates:
            return
        candidate_isbns = valid_isbns(
            value
            for candidate in candidates
            for value in (*candidate.isbns, candidate.isbn)
        )
        isbn = preferred_isbn(candidate_isbns)
        if not isbn:
            return
        project = loads_project(self.controller.project_json)
        project_volume = self._volume_number(project.metadata.title)
        relevant = tuple(
            candidate
            for candidate in candidates
            if isbn == candidate.isbn or isbn in candidate.isbns
        )
        for candidate in relevant:
            candidate_volume = self._volume_number(candidate.title)
            if (
                project_volume is not None
                and candidate_volume is not None
                and project_volume != candidate_volume
            ):
                self.status_label.setText(
                    f"搜尋結果 ISBN {isbn} 屬於第 {candidate_volume} 卷，與專案第 {project_volume} 卷不符，未套用 ISBN。"
                )
                return

        existing = normalize_isbn(project.metadata.isbn)
        if existing == isbn:
            return
        auto_apply = bool(relevant) and all(
            candidate.classification_confidence >= 0.95
            and (
                self._volume_number(candidate.title) == project_volume
                if project_volume is not None
                else self._volume_number(candidate.title) is None
            )
            for candidate in relevant
        )
        should_apply = auto_apply
        if existing and existing != isbn:
            should_apply = (
                QMessageBox.question(
                    self,
                    "確認覆蓋 ISBN",
                    f"專案已有 ISBN {existing}。是否改用搜尋結果的 {isbn}？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )
        elif not auto_apply:
            should_apply = (
                QMessageBox.question(
                    self,
                    "套用搜尋到的 ISBN",
                    f"搜尋結果找到 ISBN {isbn}。是否寫入封面專案並更新條碼？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                == QMessageBox.StandardButton.Yes
            )
        if should_apply:
            self.controller.apply_isbn(isbn)
            self.status_label.setText(f"已套用 ISBN {isbn} 並更新封底條碼。")

    def _begin_search_application(self, mode: str, selected: dict) -> None:
        if not self.controller.project_json:
            self._show_error("請先建立封面專案。")
            return
        if not selected:
            self._show_error("尚未選擇搜尋圖片。")
            return
        try:
            self._maybe_apply_search_isbn(selected)
        except Exception as exc:
            self._show_error(str(exc))
            return
        self.status_label.setText("正在下載並驗證選取的原始圖片…")
        self.search_controller.download_selected(
            selected,
            self.controller.working_dir / "assets",
            mode,
        )

    def _search_download_ready(self, mode: str, paths: dict) -> None:
        dialog = CompositionDialog(paths, mode=mode, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.status_label.setText("已取消套用搜尋圖片。")
            return
        try:
            selections = dialog.selections()
            if mode == "segmented":
                element_ids = self.controller.add_downloaded_images(selections)
                if element_ids:
                    self.canvas.select_element(element_ids[-1])
                self.status_label.setText("已將搜尋圖片加入正面／背面／書脊，可繼續裁切與移動。")
            else:
                project = loads_project(self.controller.project_json)
                destination = (
                    self.controller.working_dir
                    / "assets"
                    / f"composed-spread-{uuid4().hex}.png"
                )
                compose_full_spread(project, selections, destination, dpi=300)
                element_id = self.controller.add_composed_spread(destination)
                self.canvas.select_element(element_id)
                self.status_label.setText("已合成並套用完整書衣。")
            self.center_tabs.setCurrentIndex(0)
        except Exception as exc:
            self._show_error(str(exc))

    def _crop_asset(self, path: str) -> None:
        if not self.controller.project_json:
            return
        project = loads_project(self.controller.project_json)
        resolved_path = str(Path(path).expanduser().resolve())
        target = next(
            (
                element
                for element in project.elements
                if element.kind is ElementKind.IMAGE
                and str(Path(str(element.content.get("path", ""))).expanduser().resolve())
                == resolved_path
            ),
            None,
        )
        if target is None:
            self._show_error("找不到要裁切的封面圖片元素。")
            return
        content = target.content
        left = float(content.get("crop_left", 0.0))
        top = float(content.get("crop_top", 0.0))
        right = float(content.get("crop_right", 0.0))
        bottom = float(content.get("crop_bottom", 0.0))
        dialog = CropDialog(
            path,
            QRectF(left, top, 1.0 - left - right, 1.0 - top - bottom),
            self,
        )
        if dialog.exec():
            self.controller.update_element(target.id, {"content": dialog.crop_margins()})

    def _set_editor_mutations_enabled(self, enabled: bool) -> None:
        for widget in (
            self.template_panel,
            self.assets_panel,
            self.layers_panel,
            self.inspector,
            self.setup_panel,
            self.open_button,
            self.save_button,
            self.undo_button,
            self.redo_button,
        ):
            widget.setEnabled(enabled)
        self.export_panel.setEnabled(enabled)

    def _start_export(self, output_dir: Path | str, dpi: int) -> None:
        if not self.controller.project_json:
            self._show_error("尚未載入封面專案。")
            return
        paths = export_paths(self.controller.project_json, output_dir)
        dialog = ExportPreviewDialog(
            self.controller.project_json,
            paths,
            dpi,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.status_label.setText("已取消封面輸出。")
            return
        worker = ExportWorker(self.controller.project_json, paths, dpi)
        self._export_workers.add(worker)
        self._set_editor_mutations_enabled(False)
        worker.signals.progress.connect(self.status_label.setText)
        worker.signals.completed.connect(
            lambda result, current=worker: self._export_completed(current, result)
        )
        worker.signals.failed.connect(
            lambda message, current=worker: self._export_failed(current, message)
        )
        self.controller.pool.start(worker)

    def _export_completed(self, worker: ExportWorker, result: dict) -> None:
        self._export_workers.discard(worker)
        self._set_editor_mutations_enabled(True)
        original_pdf = result.get("original_pdf", {}).get("path", "")
        print_pdf = result.get("print_pdf", {}).get("path", "")
        print_docx = result.get("print_docx", {}).get("path", "")
        message = (
            "封面輸出完成：\n"
            f"完整尺寸 PDF：{original_pdf}\n"
            f"A4 拼接 PDF：{print_pdf}\n"
            f"A4 拼接 DOCX：{print_docx}"
        )
        self.status_label.setText(message)
        if self.isVisible():
            QMessageBox.information(self, "封面輸出完成", message)

    def _export_failed(self, worker: ExportWorker, message: str) -> None:
        self._export_workers.discard(worker)
        self._set_editor_mutations_enabled(True)
        self._show_error(message)

    def _add_text(self, region: Region) -> None:
        if not self.controller.project_json:
            self.status_label.setText("請先建立封面專案。")
            return
        project = loads_project(self.controller.project_json)
        layout = calculate_layout(project)
        target = {
            Region.FRONT: layout.front_safe_rect,
            Region.BACK: layout.back_safe_rect,
            Region.SPINE: layout.spine_safe_rect,
            Region.SPREAD: layout.spread_rect,
        }[region]
        width = max(1.0, min(target.width_mm, 80.0))
        height = max(1.0, min(target.height_mm, 20.0))
        element_id = f"local-text-{uuid4().hex}"
        highest_z = max((element.z_index for element in project.elements), default=0)
        element = CoverElement(
            id=element_id,
            kind=ElementKind.TEXT,
            region=region,
            transform=ElementTransform(
                target.x_mm + max(0.0, (target.width_mm - width) / 2.0),
                target.y_mm + max(0.0, (target.height_mm - height) / 2.0),
                width,
                height,
            ),
            z_index=highest_z + 1,
            content={
                "text": "新文字",
                "font_family": "Sans Serif",
                "font_size_pt": 18.0,
                "font_weight": 400,
                "color": "#111827",
                "align": "center",
                "line_spacing": 1.2,
                "direction": "horizontal",
            },
        )
        candidate = replace(project, elements=project.elements + (element,))
        self.controller.replace_project(dumps_project(candidate), label="加入文字")
        self.canvas.select_element(element_id)

    def _change_z_order(self, element_id: str, delta: int) -> None:
        if not self.controller.project_json:
            return
        element = loads_project(self.controller.project_json).elements_by_id[element_id]
        self.controller.update_element(element_id, {"z_index": element.z_index + int(delta)})

    def _change_visibility(self, element_id: str, visible: bool) -> None:
        self.controller.update_element(element_id, {"opacity": 1.0 if visible else 0.0})

    def _commit_canvas_transform(self, element_id: str, transform: dict) -> None:
        self.controller.update_element(element_id, {"transform": dict(transform)})

    def _project_changed(self, project_json: str) -> None:
        self.canvas.set_project(project_json)
        self.layers_panel.set_project(project_json)
        self.assets_panel.refresh_from_project(project_json)
        self.save_button.setEnabled(True)
        self.export_panel.set_project_loaded(True)
        self.inspector.set_element(None)
        project = loads_project(project_json)
        crop_blocker = QSignalBlocker(self.setup_panel.show_crop_marks_check)
        try:
            self.setup_panel.show_crop_marks_check.setChecked(
                project.export_settings.show_crop_marks
            )
        finally:
            del crop_blocker
        self._syncing_publisher_panel = True
        try:
            self.publisher_metadata_panel.set_values(asdict(project.metadata))
            self.publisher_metadata_panel.set_logo_metadata(project.metadata.publisher_logo)
        finally:
            self._syncing_publisher_panel = False
        self.publisher_metadata_panel.setEnabled(True)
        self.reset_publisher_template_button.setEnabled(True)
        self.status_label.setText(
            f"{project.metadata.title or Path(project.source_file).name}｜{project.page_count} 頁"
        )
        self.search_panel.bind_project(project_json)

    def _select_element(self, element_id: object) -> None:
        identifier = None if element_id is None else str(element_id)
        self.layers_panel.select_element(identifier)
        if identifier is None or not self.controller.project_json:
            self.inspector.set_element(None)
            return
        project = loads_project(self.controller.project_json)
        self.inspector.set_element(project.elements_by_id.get(identifier))

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        if self.isVisible():
            QMessageBox.critical(self, "封面工具", message)
