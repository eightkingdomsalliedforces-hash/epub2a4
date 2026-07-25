from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import TYPE_CHECKING
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.models import CoverProject, Region
from epub_a4_word.cover.project_io import loads_project

if TYPE_CHECKING:
    from .controller import CoverController


MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000


def _safe_name(name: str) -> str:
    filename = PurePosixPath(name.replace("\\", "/")).name
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", filename).strip("._")
    return safe or "image"


def _validate_image_bytes(data: bytes, label: str) -> tuple[int, int]:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("圖片超過 50 MiB。")
    try:
        from io import BytesIO

        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"選取的圖片無法解碼：{label}") from exc
    if width <= 0 or height <= 0:
        raise ValueError("圖片像素尺寸無效。")
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError("圖片像素尺寸超過 20000 × 20000。")
    return width, height


def _write_asset(data: bytes, source_name: str, working_dir: Path | str) -> Path:
    _validate_image_bytes(data, source_name)
    assets = Path(working_dir).expanduser().resolve() / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()[:16]
    destination = assets / f"{digest}-{_safe_name(source_name)}"
    if not destination.exists():
        destination.write_bytes(data)
    return destination.resolve()


def import_local_asset(source: Path | str, working_dir: Path | str) -> Path:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"找不到圖片：{source_path}")
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise ValueError(f"無法讀取圖片：{source_path}") from exc
    if size > MAX_IMAGE_BYTES:
        raise ValueError("圖片超過 50 MiB。")
    return _write_asset(source_path.read_bytes(), source_path.name, working_dir)


def import_embedded_asset(
    project: CoverProject,
    asset_id: str,
    working_dir: Path | str,
) -> Path:
    selected = next(
        (
            item
            for item in project.metadata.embedded_images
            if str(item.get("id", "")) == asset_id
        ),
        None,
    )
    if selected is None:
        raise KeyError(f"找不到 EPUB 內建圖片：{asset_id}")
    href = selected.get("href")
    if not isinstance(href, str) or not href.strip():
        raise ValueError("EPUB 內建圖片缺少路徑。")
    source = Path(project.source_file).expanduser().resolve()
    if project.source_type != "epub" or not source.is_file():
        raise ValueError("只有 EPUB 專案可以提取內建圖片。")
    try:
        with ZipFile(source) as archive:
            info = archive.getinfo(href)
            if info.file_size > MAX_IMAGE_BYTES:
                raise ValueError("圖片超過 50 MiB。")
            data = archive.read(info)
    except KeyError as exc:
        raise ValueError(f"EPUB 找不到內建圖片：{href}") from exc
    except BadZipFile as exc:
        raise ValueError("來源 EPUB 已損壞。") from exc
    return _write_asset(data, href, working_dir)


class AssetsPanel(QGroupBox):
    """Select local or EPUB-embedded artwork without modifying the source."""

    asset_selected = Signal(str)
    image_imported = Signal(str, object)
    add_text_requested = Signal(object)
    crop_requested = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        controller: CoverController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("素材", parent)
        self.controller = controller
        self.project_json = ""
        self._last_asset_path: Path | None = None

        self.region_combo = QComboBox(self)
        for label, region in (
            ("正面", Region.FRONT),
            ("封底", Region.BACK),
            ("書脊", Region.SPINE),
            ("完整展開", Region.SPREAD),
        ):
            self.region_combo.addItem(label, region.value)

        self.embedded_combo = QComboBox(self)
        self.embedded_combo.setPlaceholderText("EPUB 內建圖片")
        self.embedded_button = QPushButton("加入內建圖片", self)
        self.embedded_button.setEnabled(False)
        self.local_button = QPushButton("加入本機圖片", self)
        self.add_text_button = QPushButton("加入文字", self)
        self.crop_button = QPushButton("裁切最近圖片", self)
        self.crop_button.setEnabled(False)
        self.note = QLabel("PNG、JPEG、GIF、WebP；上限 50 MiB／20000 px。", self)
        self.note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.region_combo)
        layout.addWidget(self.embedded_combo)
        layout.addWidget(self.embedded_button)
        layout.addWidget(self.local_button)
        layout.addWidget(self.add_text_button)
        layout.addWidget(self.crop_button)
        layout.addWidget(self.note)

        self.embedded_button.clicked.connect(self._select_current_embedded)
        self.local_button.clicked.connect(self._pick_local)
        self.add_text_button.clicked.connect(
            lambda _checked=False: self.add_text_requested.emit(self.current_region)
        )
        self.crop_button.clicked.connect(self._request_crop)

    @property
    def current_region(self) -> Region:
        return Region(str(self.region_combo.currentData()))

    @property
    def working_dir(self) -> Path:
        if self.controller is not None:
            return self.controller.working_dir
        if self.project_json:
            project = loads_project(self.project_json)
            if project.working_dir:
                return Path(project.working_dir).expanduser().resolve()
        raise RuntimeError("尚未設定素材工作目錄。")

    def refresh_from_project(self, project_json: str) -> None:
        project = loads_project(project_json)
        self.project_json = project_json
        current_id = self.embedded_combo.currentData()
        self.embedded_combo.clear()
        for asset in project.metadata.embedded_images:
            asset_id = str(asset.get("id", "")).strip()
            if not asset_id:
                continue
            role = "封面" if asset.get("role") == "cover" else "圖片"
            dimensions = ""
            if asset.get("width_px") and asset.get("height_px"):
                dimensions = f" · {asset['width_px']}×{asset['height_px']}"
            self.embedded_combo.addItem(f"{role} · {asset_id}{dimensions}", asset_id)
        if current_id is not None:
            index = self.embedded_combo.findData(current_id)
            if index >= 0:
                self.embedded_combo.setCurrentIndex(index)
        self.embedded_button.setEnabled(self.embedded_combo.count() > 0)

    def select_embedded_asset(self, asset_id: str) -> Path:
        if not self.project_json:
            if self.controller is None or not self.controller.project_json:
                raise RuntimeError("尚未載入封面專案。")
            self.project_json = self.controller.project_json
        project = loads_project(self.project_json)
        destination = import_embedded_asset(project, asset_id, self.working_dir)
        self._emit_selected(destination)
        return destination

    def _select_current_embedded(self) -> None:
        asset_id = self.embedded_combo.currentData()
        if asset_id is None:
            return
        try:
            self.select_embedded_asset(str(asset_id))
        except Exception as exc:
            self.error.emit(str(exc))

    def _pick_local(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇封面圖片",
            "",
            "圖片 (*.png *.jpg *.jpeg *.gif *.webp)",
        )
        if not path:
            return
        try:
            destination = import_local_asset(path, self.working_dir)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self._emit_selected(destination)

    def _emit_selected(self, path: Path) -> None:
        self._last_asset_path = path
        self.crop_button.setEnabled(True)
        self.asset_selected.emit(str(path))
        self.image_imported.emit(str(path), self.current_region)

    def _request_crop(self) -> None:
        if self._last_asset_path is not None:
            self.crop_requested.emit(str(self._last_asset_path))
