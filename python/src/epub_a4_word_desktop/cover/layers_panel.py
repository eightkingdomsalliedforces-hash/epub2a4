from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.project_io import loads_project


class LayersPanel(QWidget):
    selection_changed = Signal(object)
    delete_requested = Signal(str)
    z_order_requested = Signal(str, int)
    visibility_requested = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cover-layers-panel")
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.raise_button = QPushButton("上移", self)
        self.lower_button = QPushButton("下移", self)
        self.delete_button = QPushButton("刪除", self)
        buttons = QHBoxLayout()
        buttons.addWidget(self.raise_button)
        buttons.addWidget(self.lower_button)
        buttons.addWidget(self.delete_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons)
        self._updating = False

        self.list_widget.currentItemChanged.connect(self._selection_changed)
        self.list_widget.itemChanged.connect(self._item_changed)
        self.raise_button.clicked.connect(lambda _checked=False: self._emit_z_order(1))
        self.lower_button.clicked.connect(lambda _checked=False: self._emit_z_order(-1))
        self.delete_button.clicked.connect(self._emit_delete)

    @staticmethod
    def _item_id(item: QListWidgetItem | None) -> str | None:
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def set_project(self, project_json: str) -> None:
        project = loads_project(project_json)
        selected = self._item_id(self.list_widget.currentItem())
        self._updating = True
        try:
            with QSignalBlocker(self.list_widget):
                self.list_widget.clear()
                for element in sorted(
                    project.elements,
                    key=lambda value: (value.z_index, value.id),
                    reverse=True,
                ):
                    label = str(element.content.get("text") or element.id)
                    item = QListWidgetItem(f"{label}  [{element.kind.value}]")
                    item.setData(Qt.ItemDataRole.UserRole, element.id)
                    item.setData(Qt.ItemDataRole.UserRole + 1, element.z_index)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if element.opacity > 0.0
                        else Qt.CheckState.Unchecked
                    )
                    self.list_widget.addItem(item)
                    if element.id == selected:
                        self.list_widget.setCurrentItem(item)
        finally:
            self._updating = False

    def select_element(self, element_id: str | None) -> None:
        with QSignalBlocker(self.list_widget):
            if element_id is None:
                self.list_widget.clearSelection()
                self.list_widget.setCurrentItem(None)
                return
            for row in range(self.list_widget.count()):
                item = self.list_widget.item(row)
                if self._item_id(item) == element_id:
                    self.list_widget.setCurrentItem(item)
                    return

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if not self._updating:
            self.selection_changed.emit(self._item_id(current))

    def _item_changed(self, item: QListWidgetItem) -> None:
        if self._updating:
            return
        element_id = self._item_id(item)
        if element_id is not None:
            self.visibility_requested.emit(
                element_id,
                item.checkState() == Qt.CheckState.Checked,
            )

    def _emit_z_order(self, delta: int) -> None:
        element_id = self._item_id(self.list_widget.currentItem())
        if element_id is not None:
            self.z_order_requested.emit(element_id, delta)

    def _emit_delete(self, _checked: bool = False) -> None:
        element_id = self._item_id(self.list_widget.currentItem())
        if element_id is not None:
            self.delete_requested.emit(element_id)
