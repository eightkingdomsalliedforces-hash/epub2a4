from __future__ import annotations

from dataclasses import replace
from typing import TypeVar

from PySide6.QtWidgets import QMessageBox

from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.publisher_directory import publisher_profile

_CoverPageType = TypeVar("_CoverPageType", bound=type)


def install_publisher_change_prompt(cover_page_type: _CoverPageType) -> _CoverPageType:
    """Install the publisher-change decision flow on the desktop cover page."""

    def _commit_publisher_metadata(self) -> None:
        values = self._pending_publisher_values
        self._pending_publisher_values = None
        if values is None or not self.controller.project_json:
            return

        try:
            project = loads_project(self.controller.project_json)
            previous_publisher = project.metadata.publisher.strip()
            next_publisher = values.publisher.strip()
            search_replacement_logo = False

            if next_publisher != previous_publisher:
                profile = publisher_profile(next_publisher) if next_publisher else None
                values = replace(
                    values,
                    publisher_id=profile.publisher_id if profile is not None else "",
                )
                if next_publisher:
                    answer = QMessageBox.question(
                        self,
                        "更換出版社",
                        "出版社名稱已變更。\n\n"
                        "選擇「是」：更新文字後搜尋新的出版社 Logo，並使用該出版社的搜尋設定。\n"
                        "選擇「否」：只更新出版社文字，保留目前 Logo。",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    search_replacement_logo = (
                        answer == QMessageBox.StandardButton.Yes
                    )

            self.controller.update_metadata(values.as_settings())
            if search_replacement_logo:
                self._search_publisher_logo(next_publisher)
        except Exception as exc:
            self._show_error(str(exc))

    cover_page_type._commit_publisher_metadata = _commit_publisher_metadata
    return cover_page_type
