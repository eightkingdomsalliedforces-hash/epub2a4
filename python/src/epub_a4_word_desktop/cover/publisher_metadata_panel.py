from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from epub_a4_word.cover.isbn import canonical_isbn13


@dataclass(frozen=True)
class PublisherMetadataValues:
    isbn: str = ""
    isbn_addon: str = ""
    publisher: str = ""
    price: str = ""
    publication_place: str = ""
    translator: str = ""
    publisher_id: str = ""
    english_title: str = ""
    volume_number: str = ""
    arc_label: str = ""
    series_name: str = ""
    internal_book_code: str = ""
    spine_accent_color: str = "#F15A24"

    def as_settings(self) -> dict[str, str]:
        return {
            "isbn": self.isbn,
            "isbn_addon": self.isbn_addon,
            "publisher": self.publisher,
            "price": self.price,
            "publication_place": self.publication_place,
            "translator": self.translator,
            "publisher_id": self.publisher_id,
            "english_title": self.english_title,
            "volume_number": self.volume_number,
            "arc_label": self.arc_label,
            "series_name": self.series_name,
            "internal_book_code": self.internal_book_code,
            "spine_accent_color": self.spine_accent_color,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "PublisherMetadataValues":
        data = value or {}
        return cls(
            isbn=str(data.get("isbn", "") or "").strip(),
            isbn_addon=str(data.get("isbn_addon", "") or "").strip(),
            publisher=str(data.get("publisher", "") or "").strip(),
            price=str(data.get("price", "") or "").strip(),
            publication_place=str(data.get("publication_place", "") or "").strip(),
            translator=str(data.get("translator", "") or "").strip(),
            publisher_id=str(data.get("publisher_id", "") or "").strip(),
            english_title=str(data.get("english_title", "") or "").strip(),
            volume_number=str(data.get("volume_number", "") or "").strip(),
            arc_label=str(data.get("arc_label", "") or "").strip(),
            series_name=str(data.get("series_name", "") or "").strip(),
            internal_book_code=str(data.get("internal_book_code", "") or "").strip(),
            spine_accent_color=str(
                data.get("spine_accent_color", "#F15A24") or "#F15A24"
            ).strip(),
        )


class PublisherMetadataValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class PublisherMetadataPanel(QGroupBox):
    values_changed = Signal(object)
    search_logo_requested = Signal(str)
    manual_logo_requested = Signal()
    clear_logo_requested = Signal()

    _COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("出版社封底與書脊資訊", parent)
        self.setObjectName("publisher-metadata-panel")

        self.isbn_edit = QLineEdit(self)
        self.isbn_edit.setPlaceholderText("ISBN-13 或 ISBN-10")
        self.isbn_addon_edit = QLineEdit(self)
        self.isbn_addon_edit.setPlaceholderText("2 或 5 位數，可留空")
        self.publisher_edit = QLineEdit(self)
        self.publisher_edit.setPlaceholderText("例如：台灣角川")
        self.price_edit = QLineEdit(self)
        self.price_edit.setPlaceholderText("例如：NT$110/HK$35")
        self.publication_place_edit = QLineEdit(self)
        self.publication_place_edit.setPlaceholderText("出版地、代理或發行資訊")
        self.translator_edit = QLineEdit(self)
        self.translator_edit.setPlaceholderText("例如：李彥樺")
        self.english_title_edit = QLineEdit(self)
        self.english_title_edit.setPlaceholderText("英文書名／副標題")
        self.volume_number_edit = QLineEdit(self)
        self.volume_number_edit.setPlaceholderText("集數／冊數")
        self.arc_label_edit = QLineEdit(self)
        self.arc_label_edit.setPlaceholderText("卷別／篇章")
        self.series_name_edit = QLineEdit(self)
        self.series_name_edit.setPlaceholderText("系列名稱")
        self.internal_book_code_edit = QLineEdit(self)
        self.internal_book_code_edit.setPlaceholderText("例如：CL0308-17")
        self.spine_accent_color_edit = QLineEdit("#F15A24", self)
        self.spine_accent_color_edit.setPlaceholderText("#RRGGBB")
        self.publisher_id_edit = QLineEdit(self)
        self.publisher_id_edit.setVisible(False)

        self.search_logo_button = QPushButton("搜尋出版社 Logo", self)
        self.manual_logo_button = QPushButton("手動選擇 Logo", self)
        self.clear_logo_button = QPushButton("不使用 Logo", self)
        self.logo_status_label = QLabel("尚未選擇 Logo", self)
        self.logo_status_label.setWordWrap(True)
        logo_row = QWidget(self)
        logo_layout = QHBoxLayout(logo_row)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.addWidget(self.search_logo_button)
        logo_layout.addWidget(self.manual_logo_button)
        logo_layout.addWidget(self.clear_logo_button)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("publisher-metadata-error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        form = QFormLayout()
        self._field_error_labels: dict[str, QLabel] = {}

        def add_field(label: str, field: str, widget: QWidget) -> None:
            form.addRow(label, widget)
            error = QLabel("", self)
            error.setObjectName(f"publisher-metadata-error-{field}")
            error.setWordWrap(True)
            error.hide()
            form.addRow("", error)
            self._field_error_labels[field] = error

        add_field("ISBN", "isbn", self.isbn_edit)
        add_field("ISBN 附加碼", "isbn_addon", self.isbn_addon_edit)
        add_field("出版社", "publisher", self.publisher_edit)
        add_field("定價", "price", self.price_edit)
        add_field("出版／代理資訊", "publication_place", self.publication_place_edit)
        add_field("譯者", "translator", self.translator_edit)
        add_field("英文書名／副標題", "english_title", self.english_title_edit)
        add_field("集數／冊數", "volume_number", self.volume_number_edit)
        add_field("卷別／篇章", "arc_label", self.arc_label_edit)
        add_field("系列名稱", "series_name", self.series_name_edit)
        add_field("內部書號", "internal_book_code", self.internal_book_code_edit)
        add_field("書脊強調色", "spine_accent_color", self.spine_accent_color_edit)
        form.addRow("出版社 Logo", logo_row)
        form.addRow("Logo 狀態", self.logo_status_label)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)

        self._edits = (
            self.isbn_edit,
            self.isbn_addon_edit,
            self.publisher_edit,
            self.price_edit,
            self.publication_place_edit,
            self.translator_edit,
            self.english_title_edit,
            self.volume_number_edit,
            self.arc_label_edit,
            self.series_name_edit,
            self.internal_book_code_edit,
            self.spine_accent_color_edit,
        )
        for edit in self._edits:
            edit.textChanged.connect(self._on_any_changed)
        self.search_logo_button.clicked.connect(
            lambda _checked=False: self.search_logo_requested.emit(
                self.publisher_edit.text().strip()
            )
        )
        self.manual_logo_button.clicked.connect(
            lambda _checked=False: self.manual_logo_requested.emit()
        )
        self.clear_logo_button.clicked.connect(
            lambda _checked=False: self.clear_logo_requested.emit()
        )

    def values(self) -> PublisherMetadataValues:
        raw_isbn = self.isbn_edit.text().strip()
        isbn = canonical_isbn13(raw_isbn) if raw_isbn else ""
        if raw_isbn and not isbn:
            raise PublisherMetadataValidationError(
                "isbn",
                "ISBN 必須是通過校驗的 ISBN-10 或 ISBN-13。",
            )
        addon = "".join(
            character
            for character in self.isbn_addon_edit.text()
            if character.isdigit()
        )
        raw_addon = self.isbn_addon_edit.text().strip()
        if raw_addon and (
            addon != raw_addon.replace(" ", "") or len(addon) not in {2, 5}
        ):
            raise PublisherMetadataValidationError(
                "isbn_addon",
                "ISBN 附加碼必須是 2 位或 5 位數字。",
            )
        color = self.spine_accent_color_edit.text().strip() or "#F15A24"
        if not self._COLOR_RE.fullmatch(color):
            raise PublisherMetadataValidationError(
                "spine_accent_color",
                "書脊強調色必須使用 #RRGGBB 格式。",
            )
        return PublisherMetadataValues(
            isbn=isbn,
            isbn_addon=addon,
            publisher=self.publisher_edit.text().strip(),
            price=self.price_edit.text().strip(),
            publication_place=self.publication_place_edit.text().strip(),
            translator=self.translator_edit.text().strip(),
            publisher_id=self.publisher_id_edit.text().strip(),
            english_title=self.english_title_edit.text().strip(),
            volume_number=self.volume_number_edit.text().strip(),
            arc_label=self.arc_label_edit.text().strip(),
            series_name=self.series_name_edit.text().strip(),
            internal_book_code=self.internal_book_code_edit.text().strip(),
            spine_accent_color=color.upper(),
        )

    def set_values(self, values: PublisherMetadataValues | Mapping[str, object]) -> None:
        normalized = (
            values
            if isinstance(values, PublisherMetadataValues)
            else PublisherMetadataValues.from_mapping(values)
        )
        pairs = (
            (self.isbn_edit, normalized.isbn),
            (self.isbn_addon_edit, normalized.isbn_addon),
            (self.publisher_edit, normalized.publisher),
            (self.price_edit, normalized.price),
            (self.publication_place_edit, normalized.publication_place),
            (self.translator_edit, normalized.translator),
            (self.publisher_id_edit, normalized.publisher_id),
            (self.english_title_edit, normalized.english_title),
            (self.volume_number_edit, normalized.volume_number),
            (self.arc_label_edit, normalized.arc_label),
            (self.series_name_edit, normalized.series_name),
            (self.internal_book_code_edit, normalized.internal_book_code),
            (self.spine_accent_color_edit, normalized.spine_accent_color),
        )
        blockers = [QSignalBlocker(edit) for edit, _text in pairs]
        try:
            for edit, text in pairs:
                edit.setText(text)
        finally:
            del blockers
        self.clear_validation_error()

    def set_logo_metadata(self, value: object) -> None:
        if value is None:
            self.logo_status_label.setText("尚未選擇 Logo")
            return
        source = str(getattr(value, "source_category", "") or "")
        filename = Path(str(getattr(value, "path", "") or "")).name
        manual = bool(getattr(value, "manual_selection", False))
        origin = "手動圖片" if manual else (source or "已下載")
        self.logo_status_label.setText(
            f"{filename or '已選擇 Logo'} · {origin}"
        )

    def set_validation_error(self, field: str, message: str) -> None:
        self.clear_validation_error()
        label = self._field_error_labels.get(field)
        if label is None:
            self.error_label.setText(message)
            self.error_label.setVisible(bool(message))
            return
        label.setText(message)
        label.setVisible(bool(message))

    def clear_validation_error(self, field: str | None = None) -> None:
        labels = (
            (self._field_error_labels[field],)
            if field in self._field_error_labels
            else tuple(self._field_error_labels.values())
        )
        for label in labels:
            label.clear()
            label.hide()
        if field is None or field not in self._field_error_labels:
            self.error_label.clear()
            self.error_label.hide()

    def _on_any_changed(self, _text: str) -> None:
        self.clear_validation_error()
        try:
            values = self.values()
        except PublisherMetadataValidationError as exc:
            self.set_validation_error(exc.field, str(exc))
            return
        except ValueError as exc:
            self.set_validation_error("", str(exc))
            return
        self.values_changed.emit(values)
