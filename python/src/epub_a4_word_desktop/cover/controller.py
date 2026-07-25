from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Protocol
from uuid import uuid4

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QUndoStack

from epub_a4_word.cover import service as shared_service
from epub_a4_word.cover.composition import CompositionSelection
from epub_a4_word.cover.geometry import calculate_layout
from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    ElementKind,
    ElementTransform,
    Region,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word.cover.search.models import CandidateCategory

from .commands import ReplaceProjectCommand
from .models import patch_element


class CoverService(Protocol):
    def new_project(self, source_path: str, settings_json: str) -> str: ...
    def apply_template(self, project_json: str, template_id: str) -> str: ...
    def render_preview(
        self,
        project_json: str,
        output_png: str,
        max_px: int = 1600,
    ) -> dict[str, Any]: ...


class WorkerPool(Protocol):
    def start(self, worker: QRunnable) -> None: ...


class PreviewWorkerSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, str)


class PreviewWorker(QRunnable):
    def __init__(
        self,
        service: CoverService,
        project_json: str,
        output_path: Path,
        generation: int,
    ) -> None:
        super().__init__()
        self.service = service
        self.project_json = project_json
        self.output_path = output_path
        self.generation = generation
        self.signals = PreviewWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.render_preview(
                self.project_json,
                str(self.output_path),
                max_px=1600,
            )
            path = Path(str(result["path"]))
        except Exception as exc:
            self.signals.failed.emit(self.generation, str(exc))
        else:
            self.signals.completed.emit(self.generation, path)


class CoverController(QObject):
    project_changed = Signal(str)
    preview_ready = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        service: CoverService | None = None,
        pool: WorkerPool | None = None,
        working_dir: Path | str | None = None,
        auto_preview: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.service: CoverService = service or shared_service
        self.pool: WorkerPool = pool or QThreadPool.globalInstance()
        self.working_dir = Path(
            working_dir or tempfile.mkdtemp(prefix="epub2a4-cover-")
        ).expanduser().resolve()
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.undo_stack = QUndoStack(self)
        self.project_json = ""
        self.auto_preview = auto_preview
        self._preview_generation = 0
        self._preview_workers: dict[int, PreviewWorker] = {}
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._start_preview)

    @property
    def can_undo(self) -> bool:
        return self.undo_stack.canUndo()

    @property
    def can_redo(self) -> bool:
        return self.undo_stack.canRedo()

    def _require_project(self) -> CoverProject:
        if not self.project_json:
            raise RuntimeError("尚未載入封面專案。")
        return loads_project(self.project_json)

    def _set_project_json(self, project_json: str) -> None:
        canonical = dumps_project(loads_project(project_json))
        self.project_json = canonical
        self.project_changed.emit(canonical)
        if self.auto_preview:
            self.schedule_preview()

    def replace_project(
        self,
        project_json: str,
        *,
        clear_history: bool = False,
        label: str = "取代封面專案",
    ) -> None:
        canonical = dumps_project(loads_project(project_json))
        if clear_history or not self.project_json:
            self.undo_stack.clear()
            self._set_project_json(canonical)
            return
        if canonical == self.project_json:
            return
        self.undo_stack.push(
            ReplaceProjectCommand(self, self.project_json, canonical, label)
        )

    def load_source(
        self,
        source_path: Path | str,
        settings: Mapping[str, Any] | str | None = None,
    ) -> str:
        if settings is None:
            settings_value: Mapping[str, Any] = {
                "working_dir": str(self.working_dir),
                "trim_width_mm": 148.0,
                "trim_height_mm": 210.0,
                "paper_caliper_mm": 0.10,
                "manual_spine_width_mm": None,
                "bleed_mm": 3.0,
                "overlap_mm": 5.0,
                "dpi": 300,
                "show_crop_marks": True,
                "show_assembly_marks": True,
            }
            settings_json = json.dumps(settings_value, ensure_ascii=False)
        elif isinstance(settings, str):
            settings_json = settings
        else:
            settings_value = dict(settings)
            settings_value.setdefault("working_dir", str(self.working_dir))
            settings_json = json.dumps(settings_value, ensure_ascii=False)
        project_json = self.service.new_project(str(source_path), settings_json)
        self.replace_project(project_json, clear_history=True)
        return self.project_json

    def apply_template(self, template_id: str) -> None:
        current = self._require_project()
        candidate_json = self.service.apply_template(dumps_project(current), template_id)
        self.replace_project(candidate_json, label=f"套用模板：{template_id}")

    def update_element(self, element_id: str, patch: Mapping[str, Any]) -> None:
        candidate = patch_element(self._require_project(), element_id, patch)
        candidate_json = dumps_project(candidate)
        loads_project(candidate_json)
        self.replace_project(candidate_json, label="更新封面元素")

    @staticmethod
    def _safe_asset_name(name: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z._-]+", "_", Path(name).name).strip("._")
        return safe or "image"

    def _copy_local_image(self, source: Path) -> Path:
        if not source.is_file():
            raise ValueError(f"找不到圖片：{source}")
        try:
            with Image.open(source) as image:
                image.verify()
        except Exception as exc:
            raise ValueError("選取的檔案不是可用圖片。") from exc
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()[:16]
        assets_dir = (self.working_dir / "assets").resolve()
        assets_dir.mkdir(parents=True, exist_ok=True)
        destination = assets_dir / f"{digest}-{self._safe_asset_name(source.name)}"
        if not destination.exists():
            shutil.copyfile(source, destination)
        return destination.resolve()

    @staticmethod
    def _target_rect(project: CoverProject, region: Region):
        layout = calculate_layout(project)
        return {
            Region.BACK: layout.back_rect,
            Region.SPINE: layout.spine_rect,
            Region.FRONT: layout.front_rect,
            Region.SPREAD: layout.bleed_rect,
        }[region]

    @staticmethod
    def _region_for_category(category: CandidateCategory | str) -> Region:
        value = CandidateCategory(category)
        return {
            CandidateCategory.BACK: Region.BACK,
            CandidateCategory.SPINE: Region.SPINE,
            CandidateCategory.FRONT: Region.FRONT,
            CandidateCategory.FULL_SPREAD: Region.SPREAD,
        }[value]

    def _image_element(
        self,
        project: CoverProject,
        source: Path,
        region: Region,
        *,
        selection: CompositionSelection | None = None,
        z_index: int,
        element_id: str | None = None,
    ) -> CoverElement:
        copied = self._copy_local_image(source)
        target = self._target_rect(project, region)
        scale = selection.scale if selection else 1.0
        offset_x = selection.offset_x if selection else 0.0
        offset_y = selection.offset_y if selection else 0.0
        width = target.width_mm * scale
        height = target.height_mm * scale
        transform = ElementTransform(
            target.x_mm + (target.width_mm - width) / 2.0 + offset_x * target.width_mm,
            target.y_mm + (target.height_mm - height) / 2.0 + offset_y * target.height_mm,
            width,
            height,
        )
        content: dict[str, Any] = {"path": str(copied), "fit": "cover"}
        if selection:
            content.update(
                {
                    "crop_left": selection.crop_left,
                    "crop_top": selection.crop_top,
                    "crop_right": selection.crop_right,
                    "crop_bottom": selection.crop_bottom,
                }
            )
        return CoverElement(
            id=element_id or f"downloaded-image-{uuid4().hex}",
            kind=ElementKind.IMAGE,
            region=region,
            transform=transform,
            z_index=z_index,
            content=content,
        )

    def add_local_image(self, source_path: Path | str, region: Region | str) -> str:
        project = self._require_project()
        selected_region = region if isinstance(region, Region) else Region(str(region))
        highest_z = max((element.z_index for element in project.elements), default=0)
        element = self._image_element(
            project,
            Path(source_path).expanduser().resolve(),
            selected_region,
            z_index=highest_z + 1,
            element_id=f"local-image-{uuid4().hex}",
        )
        candidate = replace(project, elements=project.elements + (element,))
        self.replace_project(dumps_project(candidate), label="加入本機圖片")
        return element.id

    def add_downloaded_images(
        self,
        selections: Mapping[CandidateCategory | str, CompositionSelection],
    ) -> tuple[str, ...]:
        project = self._require_project()
        elements = list(project.elements)
        highest_z = max((element.z_index for element in elements), default=0)
        added: list[str] = []
        order = (
            CandidateCategory.BACK,
            CandidateCategory.SPINE,
            CandidateCategory.FRONT,
        )
        normalized = {CandidateCategory(key): value for key, value in selections.items()}
        for category in order:
            selection = normalized.get(category)
            if selection is None:
                continue
            highest_z += 1
            element = self._image_element(
                project,
                selection.path,
                self._region_for_category(category),
                selection=selection,
                z_index=highest_z,
            )
            elements.append(element)
            added.append(element.id)
        if not added:
            raise ValueError("沒有可套用到正面、背面或書脊的圖片。")
        self.replace_project(
            dumps_project(replace(project, elements=tuple(elements))),
            label="套用搜尋封面分區圖片",
        )
        return tuple(added)

    def add_composed_spread(self, source_path: Path | str) -> str:
        project = self._require_project()
        highest_z = max((element.z_index for element in project.elements), default=0)
        element = self._image_element(
            project,
            Path(source_path).expanduser().resolve(),
            Region.SPREAD,
            z_index=highest_z + 1,
            element_id=f"composed-spread-{uuid4().hex}",
        )
        self.replace_project(
            dumps_project(replace(project, elements=project.elements + (element,))),
            label="套用合成完整書衣",
        )
        return element.id

    def remove_element(self, element_id: str) -> None:
        project = self._require_project()
        if element_id not in project.elements_by_id:
            raise KeyError(f"找不到封面元素：{element_id}")
        candidate = replace(
            project,
            elements=tuple(item for item in project.elements if item.id != element_id),
        )
        self.replace_project(dumps_project(candidate), label="刪除封面元素")

    def undo(self) -> None:
        self.undo_stack.undo()

    def redo(self) -> None:
        self.undo_stack.redo()

    def schedule_preview(self) -> None:
        if not self.project_json:
            return
        self._preview_generation += 1
        self._preview_timer.start()

    @Slot()
    def _start_preview(self) -> None:
        if not self.project_json:
            return
        generation = self._preview_generation
        preview_dir = self.working_dir / "previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        worker = PreviewWorker(
            self.service,
            self.project_json,
            preview_dir / f"preview-{generation}.png",
            generation,
        )
        worker.signals.completed.connect(self._accept_preview)
        worker.signals.failed.connect(self._preview_failed)
        self._preview_workers[generation] = worker
        self.pool.start(worker)

    @Slot(int, object)
    def _accept_preview(self, generation: int, path: Path) -> None:
        self._preview_workers.pop(generation, None)
        if generation == self._preview_generation:
            self.preview_ready.emit(Path(path))

    @Slot(int, str)
    def _preview_failed(self, generation: int, message: str) -> None:
        self._preview_workers.pop(generation, None)
        if generation == self._preview_generation:
            self.error.emit(message)
