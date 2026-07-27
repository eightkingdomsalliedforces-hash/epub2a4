from __future__ import annotations

from pathlib import Path

path = Path("python/src/epub_a4_word_desktop/pages/cover_page.py")
text = path.read_text(encoding="utf-8")
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
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one publisher metadata method, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
