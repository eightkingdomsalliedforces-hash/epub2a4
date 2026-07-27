from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
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
from epub_a4_word.cover.geometry import RectMm, calculate_layout
from epub_a4_word.cover.isbn import canonical_isbn13
from epub_a4_word.cover.models import (
    CoverElement,
    CoverProject,
    LogoAssetMetadata,
    ElementKind,
    ElementTransform,
    Region,
)
from epub_a4_word.cover.project_io import dumps_project, loads_project
from epub_a4_word.cover.search.logo_download import DownloadedLogo, import_logo_file
from epub_a4_word.cover.search.logo_models import LogoCandidate, LogoSourceCategory
from epub_a4_word.cover.search.models import CandidateCategory
from epub_a4_word.cover.templates import (
    apply_template as apply_cover_template,
    refresh_template_metadata,
)

from .commands import ReplaceProjectCommand
from .models import patch_element
from .svg_logo import rasterize_svg_logo


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

    def update_metadata(
        self,
        patch: Mapping[str, object],
        *,
        reset_layout: bool = False,
    ) -> None:
        project = self._require_project()
        allowed = set(project.metadata.__dataclass_fields__)
        unknown = sorted(set(patch) - allowed)
        if unknown:
            raise ValueError("不支援的封面資訊：" + "、".join(unknown))
        metadata = replace(project.metadata, **dict(patch))
        candidate = refresh_template_metadata(
            project,
            metadata,
            reset_layout=reset_layout,
        )
        self.replace_project(
            dumps_project(candidate),
            label="重設出版社模板版面" if reset_layout else "更新出版社資訊",
        )

    def apply_publisher_logo(
        self,
        downloaded: DownloadedLogo,
        candidate: LogoCandidate | None = None,
        *,
        manual_selection: bool = False,
    ) -> str:
        project = self._require_project()
        assets_dir = (self.working_dir / "assets").resolve()
        assets_dir.mkdir(parents=True, exist_ok=True)
        suffix = downloaded.path.suffix.casefold() or ".img"
        asset_id = f"publisher-logo-{downloaded.sha256[:16]}"
        destination = assets_dir / f"{asset_id}{suffix}"
        if downloaded.path.resolve() != destination.resolve() and not destination.exists():
            shutil.copyfile(downloaded.path, destination)
        source_category = (
            LogoSourceCategory.MANUAL.value
            if manual_selection or candidate is None
            else candidate.source_category.value
        )
        logo = LogoAssetMetadata(
            asset_id=asset_id,
            path=str(destination.resolve()),
            source_url=(
                "" if manual_selection or candidate is None else candidate.image_url
            ),
            source_category=source_category,
            downloaded_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            image_format=downloaded.image_format,
            width_px=downloaded.width_px,
            height_px=downloaded.height_px,
            license_text=(
                "" if candidate is None else candidate.license_text
            ),
            official_source=(
                False if candidate is None else candidate.official_source
            ),
            manual_selection=bool(manual_selection),
        )
        self.update_metadata({"publisher_logo": logo})
        return asset_id

    def apply_manual_publisher_logo(self, source_path: Path | str) -> str:
        downloaded = import_logo_file(
            source_path,
            self.working_dir / "logo-imports",
            svg_converter=rasterize_svg_logo,
        )
        return self.apply_publisher_logo(
            downloaded,
            manual_selection=True,
        )

    def clear_publisher_logo(self) -> None:
        self.update_metadata({"publisher_logo": None})

    def apply_isbn(self, value: object) -> str:
        isbn = canonical_isbn13(value)
        if not isbn:
            raise ValueError("ISBN 必須是通過校驗的 ISBN-10 或 ISBN-13。")
        project = self._require_project()
        metadata = replace(project.metadata, isbn=isbn)
        active_template = str(project.background.get("active_template", ""))
        if active_template in {
            "publisher_back_matter",
            "publisher_back_matter_with_spine",
        }:
            candidate = refresh_template_metadata(project, metadata)
        else:
            candidate = replace(project, metadata=metadata)
            updated = []
            for element in candidate.elements:
                content = dict(element.content)
                if element.kind is ElementKind.BARCODE_PLACEHOLDER:
                    content["isbn"] = isbn
                    content["text"] = isbn
                elif element.id == "back-isbn-label":
                    content["text"] = f"ISBN {isbn}"
                updated.append(replace(element, content=content))
            candidate = replace(candidate, elements=tuple(updated))
        self.replace_project(dumps_project(candidate), label="套用 ISBN")
        return isbn

    @staticmethod
    def _group_id(element: CoverElement) -> str:
        value = element.content.get("group_id", "")
        return str(value).strip() if isinstance(value, str) else ""

    @classmethod
    def _group_members_from_project(
        cls,
        project: CoverProject,
        element_id: str,
    ) -> tuple[CoverElement, ...]:
        try:
            target = project.elements_by_id[element_id]
        except KeyError as exc:
            raise KeyError(f"找不到封面元素：{element_id}") from exc
        group_id = cls._group_id(target)
        if not group_id:
            return (target,)
        return tuple(
            element
            for element in project.elements
            if cls._group_id(element) == group_id
        )

    def group_members(self, element_id: str) -> tuple[CoverElement, ...]:
        return self._group_members_from_project(self._require_project(), element_id)

    @staticmethod
    def _scaled_group_content(
        content: Mapping[str, Any],
        *,
        font_scale: float,
        vertical_scale: float,
    ) -> dict[str, Any]:
        updated = dict(content)
        font_size = updated.get("font_size_pt")
        if isinstance(font_size, (int, float)) and not isinstance(font_size, bool):
            updated["font_size_pt"] = float(font_size) * font_scale
        line_spacing_mm = updated.get("line_spacing_mm")
        if isinstance(line_spacing_mm, (int, float)) and not isinstance(
            line_spacing_mm, bool
        ):
            updated["line_spacing_mm"] = float(line_spacing_mm) * vertical_scale
        return updated

    @classmethod
    def _patch_group_transform(
        cls,
        project: CoverProject,
        element_id: str,
        transform_patch: object,
    ) -> CoverProject:
        members = cls._group_members_from_project(project, element_id)
        target = project.elements_by_id[element_id]
        patched = patch_element(
            project,
            element_id,
            {"transform": transform_patch},
        ).elements_by_id[element_id]
        old_transform = target.transform
        new_transform = patched.transform
        scale_x = new_transform.width_mm / old_transform.width_mm
        scale_y = new_transform.height_mm / old_transform.height_mm
        font_scale = min(scale_x, scale_y)
        rotation_delta = new_transform.rotation_deg - old_transform.rotation_deg
        member_ids = {member.id for member in members}
        replacements: dict[str, CoverElement] = {}
        for member in members:
            if member.id == element_id:
                member_transform = new_transform
            else:
                member_transform = ElementTransform(
                    x_mm=new_transform.x_mm
                    + (member.transform.x_mm - old_transform.x_mm) * scale_x,
                    y_mm=new_transform.y_mm
                    + (member.transform.y_mm - old_transform.y_mm) * scale_y,
                    width_mm=member.transform.width_mm * scale_x,
                    height_mm=member.transform.height_mm * scale_y,
                    rotation_deg=member.transform.rotation_deg + rotation_delta,
                )
            replacements[member.id] = replace(
                member,
                transform=member_transform,
                content=cls._scaled_group_content(
                    member.content,
                    font_scale=font_scale,
                    vertical_scale=scale_y,
                ),
            )
        return replace(
            project,
            elements=tuple(
                replacements.get(element.id, element)
                if element.id in member_ids
                else element
                for element in project.elements
            ),
        )

    def update_element(self, element_id: str, patch: Mapping[str, Any]) -> None:
        project = self._require_project()
        members = self._group_members_from_project(project, element_id)
        is_group = len(members) > 1
        patch_keys = set(patch)
        if is_group and patch_keys == {"transform"}:
            candidate = self._patch_group_transform(
                project,
                element_id,
                patch["transform"],
            )
            label = "更新出版資訊群組"
        elif is_group and patch_keys == {"opacity"}:
            opacity = float(patch["opacity"])
            member_ids = {member.id for member in members}
            candidate = replace(
                project,
                elements=tuple(
                    replace(element, opacity=opacity)
                    if element.id in member_ids
                    else element
                    for element in project.elements
                ),
            )
            label = "切換出版資訊群組顯示"
        elif is_group and patch_keys == {"z_index"}:
            target = project.elements_by_id[element_id]
            delta = int(patch["z_index"]) - target.z_index
            member_ids = {member.id for member in members}
            candidate = replace(
                project,
                elements=tuple(
                    replace(element, z_index=element.z_index + delta)
                    if element.id in member_ids
                    else element
                    for element in project.elements
                ),
            )
            label = "調整出版資訊群組圖層"
        else:
            candidate = patch_element(project, element_id, patch)
            label = "更新封面元素"
        candidate_json = dumps_project(candidate)
        loads_project(candidate_json)
        self.replace_project(candidate_json, label=label)

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
    def _uses_publisher_logo_slot(project: CoverProject, region: Region) -> bool:
        return (
            region is Region.BACK
            and str(project.background.get("active_template", ""))
            in {"publisher_back_matter", "publisher_back_matter_with_spine"}
            and isinstance(project.background.get("publisher_logo_slot"), Mapping)
        )

    @staticmethod
    def _target_rect(project: CoverProject, region: Region):
        layout = calculate_layout(project)
        if CoverController._uses_publisher_logo_slot(project, region):
            slot = project.background.get("publisher_logo_slot")
            if isinstance(slot, Mapping):
                try:
                    return RectMm(
                        float(slot["x_mm"]),
                        float(slot["y_mm"]),
                        float(slot["width_mm"]),
                        float(slot["height_mm"]),
                    )
                except (KeyError, TypeError, ValueError):
                    pass
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
        transform = ElementTransform(
            target.x_mm,
            target.y_mm,
            target.width_mm,
            target.height_mm,
        )
        content: dict[str, Any] = {
            "path": str(copied),
            "fit": "contain" if self._uses_publisher_logo_slot(project, region) else "cover",
            "scale": selection.scale if selection else 1.0,
            "offset_x": selection.offset_x if selection else 0.0,
            "offset_y": selection.offset_y if selection else 0.0,
        }
        if selection:
            content.update(
                {
                    "crop": {
                        "left": selection.crop_left,
                        "top": selection.crop_top,
                        "right": 1.0 - selection.crop_right,
                        "bottom": 1.0 - selection.crop_bottom,
                    },
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

    @staticmethod
    def _without_replaced_cover_images(
        elements: list[CoverElement],
        replacement_regions: set[Region],
    ) -> list[CoverElement]:
        replace_spread = Region.SPREAD in replacement_regions
        return [
            element
            for element in elements
            if not (
                element.kind is ElementKind.IMAGE
                and (
                    replace_spread
                    or element.region is Region.SPREAD
                    or element.region in replacement_regions
                )
            )
        ]

    def add_downloaded_images(
        self,
        selections: Mapping[CandidateCategory | str, CompositionSelection],
    ) -> tuple[str, ...]:
        project = self._require_project()
        added: list[str] = []
        order = (
            CandidateCategory.BACK,
            CandidateCategory.SPINE,
            CandidateCategory.FRONT,
        )
        normalized = {CandidateCategory(key): value for key, value in selections.items()}
        replacement_regions = {
            self._region_for_category(category)
            for category in normalized
            if category in order
        }
        elements = self._without_replaced_cover_images(
            list(project.elements), replacement_regions
        )
        highest_z = max((element.z_index for element in elements), default=0)
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
        retained = self._without_replaced_cover_images(
            list(project.elements), {Region.SPREAD}
        )
        highest_z = max((element.z_index for element in retained), default=0)
        element = self._image_element(
            project,
            Path(source_path).expanduser().resolve(),
            Region.SPREAD,
            z_index=highest_z + 1,
            element_id=f"composed-spread-{uuid4().hex}",
        )
        self.replace_project(
            dumps_project(replace(project, elements=tuple(retained) + (element,))),
            label="套用合成完整書衣",
        )
        return element.id

    def remove_element(self, element_id: str) -> None:
        project = self._require_project()
        members = self._group_members_from_project(project, element_id)
        member_ids = {member.id for member in members}
        candidate = replace(
            project,
            elements=tuple(
                item for item in project.elements if item.id not in member_ids
            ),
        )
        label = "刪除出版資訊群組" if len(members) > 1 else "刪除封面元素"
        self.replace_project(dumps_project(candidate), label=label)

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
        project = self._require_project()
        raster_project = replace(
            project,
            elements=tuple(
                element
                for element in project.elements
                if element.kind
                not in {
                    ElementKind.IMAGE,
                    ElementKind.TEXT,
                    ElementKind.BARCODE_PLACEHOLDER,
                }
            ),
        )
        worker = PreviewWorker(
            self.service,
            dumps_project(raster_project),
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
