from __future__ import annotations

from pathlib import Path


path = Path("python/src/epub_a4_word_desktop/pages/cover_page.py")
text = path.read_text("utf-8")
old = '''    def _commit_publisher_metadata(self) -> None:
        values = self._pending_publisher_values
        self._pending_publisher_values = None
        if values is None or not self.controller.project_json:
            return
        try:
            self.controller.update_metadata(values.as_settings())
        except Exception as exc:
            self._show_error(str(exc))
'''
new = '''    def _commit_publisher_metadata(self) -> None:
        values = self._pending_publisher_values
        self._pending_publisher_values = None
        if values is None or not self.controller.project_json:
            return
        project = loads_project(self.controller.project_json)
        previous_publisher = project.metadata.publisher.strip()
        new_publisher = values.publisher.strip()
        publisher_changed = bool(new_publisher) and (
            previous_publisher.casefold() != new_publisher.casefold()
        )
        try:
            self.controller.update_metadata(values.as_settings())
        except Exception as exc:
            self._show_error(str(exc))
            return
        if not publisher_changed:
            return
        description = (
            f"出版社已由「{previous_publisher}」改為「{new_publisher}」。"
            if previous_publisher
            else f"出版社已設定為「{new_publisher}」。"
        )
        should_search = (
            QMessageBox.question(
                self,
                "搜尋替換出版社 Logo",
                description + "是否搜尋新出版社的 Logo 候選？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        )
        if should_search:
            self._search_publisher_logo(new_publisher)
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one publisher metadata commit block, found {count}")
path.write_text(text.replace(old, new, 1), "utf-8")
