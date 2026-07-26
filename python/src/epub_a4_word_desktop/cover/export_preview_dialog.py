from __future__ import annotations

from io import BytesIO

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.export_plan import build_export_plan
from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.render import render_print_page

from .export_worker import ExportPaths


class ExportPreviewDialog(QDialog):
    def __init__(
        self,
        project_json: str,
        paths: ExportPaths,
        dpi: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("確認封面輸出")
        self.resize(860, 680)
        self.project_json = project_json
        self.paths = paths
        self.dpi = int(dpi)
        self.confirmed_export = False

        project = loads_project(project_json)
        self.export_plan = build_export_plan(project)
        width_mm, height_mm = self.export_plan.original_size_mm
        page_count = len(self.export_plan.print_plan.pages)
        self.summary_label = QLabel(
            f"完整書衣：{width_mm:.1f} × {height_mm:.1f} mm｜"
            f"A4 拼接：{page_count} 頁｜"
            f"重疊區：{self.export_plan.overlap_mm:.1f} mm",
            self,
        )
        self.summary_label.setWordWrap(True)
        self.files_label = QLabel(
            "即將輸出：\n"
            f"{paths.original_pdf.name}\n"
            f"{paths.print_pdf.name}\n"
            f"{paths.print_docx.name}",
            self,
        )
        self.files_label.setWordWrap(True)

        preview_host = QWidget(self)
        preview_layout = QHBoxLayout(preview_host)
        self.page_labels: list[QLabel] = []
        for page in self.export_plan.print_plan.pages:
            column = QWidget(preview_host)
            column_layout = QVBoxLayout(column)
            label_text = next(
                (
                    mark.label
                    for mark in page.marks
                    if mark.kind == "label" and mark.role == "label"
                ),
                page.name,
            )
            page_label = QLabel(label_text, column)
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.page_labels.append(page_label)

            image = render_print_page(project, page, dpi=72)
            stream = BytesIO()
            image.save(stream, format="PNG")
            image.close()
            pixmap = QPixmap()
            pixmap.loadFromData(stream.getvalue(), "PNG")
            thumbnail = QLabel(column)
            thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumbnail.setPixmap(
                pixmap.scaled(
                    300,
                    420,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            column_layout.addWidget(page_label)
            column_layout.addWidget(thumbnail, 1)
            preview_layout.addWidget(column)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(preview_host)

        self.blank_back_warning = QLabel(
            "封底目前為空白。請返回補上封底，或明確選擇仍然輸出空白封底。",
            self,
        )
        self.blank_back_warning.setWordWrap(True)
        self.blank_back_warning.setVisible(self.export_plan.back_cover_blank)
        self.return_button = QPushButton("返回補上封底", self)
        self.continue_blank_button = QPushButton("仍然輸出空白封底", self)
        self.return_button.setVisible(self.export_plan.back_cover_blank)
        self.continue_blank_button.setVisible(self.export_plan.back_cover_blank)

        self.cancel_button = QPushButton("取消", self)
        self.export_button = QPushButton("開始輸出三個檔案", self)
        if not self.export_plan.back_cover_blank:
            self.confirmed_export = True
        self.export_button.setEnabled(self.confirmed_export)

        blank_actions = QHBoxLayout()
        blank_actions.addWidget(self.return_button)
        blank_actions.addWidget(self.continue_blank_button)
        blank_actions.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.files_label)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.blank_back_warning)
        layout.addLayout(blank_actions)
        layout.addLayout(actions)

        self.return_button.clicked.connect(self.reject)
        self.continue_blank_button.clicked.connect(self._confirm_blank_back)
        self.cancel_button.clicked.connect(self.reject)
        self.export_button.clicked.connect(self._accept_export)

    def _confirm_blank_back(self) -> None:
        self.confirmed_export = True
        self.export_button.setEnabled(True)
        self.blank_back_warning.setText("已確認：仍然輸出空白封底。")

    def _accept_export(self) -> None:
        if self.confirmed_export:
            self.accept()
