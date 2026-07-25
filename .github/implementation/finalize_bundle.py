from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text("utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch target in {path}, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), "utf-8")


panel = Path("python/src/epub_a4_word_desktop/cover/search_panel.py")
replace_once(
    panel,
    """            pixmap.scaled(
                self.preview.size(),
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                transformMode=Qt.TransformationMode.SmoothTransformation,
            )
""",
    """            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
""",
)
replace_once(
    panel,
    "        self.cards: list[CandidateCard] = []\n        self.network = QNetworkAccessManager(self)\n",
    "        self.cards: list[CandidateCard] = []\n        self._columns = 0\n        self.network = QNetworkAccessManager(self)\n",
)
replace_once(
    panel,
    "        persistent_available: bool = True,\n        parent: QWidget | None = None,\n",
    "        persistent_available: bool = True,\n        auto_search: bool = True,\n        parent: QWidget | None = None,\n",
)
replace_once(
    panel,
    "        self.persistent_available = persistent_available\n        self.metadata: dict[str, object] = {}\n",
    "        self.persistent_available = persistent_available\n        self.auto_search = bool(auto_search)\n        self.metadata: dict[str, object] = {}\n",
)
replace_once(
    panel,
    "        self._rebuild_cards()\n        self._update_selection_summary()\n        self._search_public()\n",
    "        self._rebuild_cards()\n        self._update_selection_summary()\n        if not self.auto_search:\n            self.status_label.setText(\"封面搜尋已準備完成；按搜尋按鈕後才會連線。\")\n            self._update_credential_state()\n            return\n        self._search_public()\n",
)
replace_once(
    panel,
    "        columns = max(1, self.scroll.viewport().width() // 235)\n        for index, candidate in enumerate(ordered):\n",
    "        columns = max(1, self.scroll.viewport().width() // 235)\n        self._columns = columns\n        for index, candidate in enumerate(ordered):\n",
)
replace_once(
    panel,
    """    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.cards:
            self._rebuild_cards()
""",
    """    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        columns = max(1, self.scroll.viewport().width() // 235)
        if self.cards and columns != self._columns:
            self._rebuild_cards()
""",
)

cover_page = Path("python/src/epub_a4_word_desktop/pages/cover_page.py")
replace_once(
    cover_page,
    "            persistent_available=persistent_available,\n            parent=self,\n",
    "            persistent_available=persistent_available,\n            auto_search=runtime_paths is not None,\n            parent=self,\n",
)

preview = Path("python/src/epub_a4_word_desktop/conversion/layout_preview.py")
replace_once(
    preview,
    "from PySide6.QtCore import QRectF, Qt",
    "from PySide6.QtCore import QLineF, QRectF, Qt",
)
replace_once(
    preview,
    "                painter.drawLine(x, trim.top() - gap - length, x, trim.top() - gap)\n                painter.drawLine(x, trim.bottom() + gap, x, trim.bottom() + gap + length)\n",
    "                painter.drawLine(QLineF(x, trim.top() - gap - length, x, trim.top() - gap))\n                painter.drawLine(QLineF(x, trim.bottom() + gap, x, trim.bottom() + gap + length))\n",
)
replace_once(
    preview,
    "                painter.drawLine(trim.left() - gap - length, y, trim.left() - gap, y)\n                painter.drawLine(trim.right() + gap, y, trim.right() + gap + length, y)\n",
    "                painter.drawLine(QLineF(trim.left() - gap - length, y, trim.left() - gap, y))\n                painter.drawLine(QLineF(trim.right() + gap, y, trim.right() + gap + length, y))\n",
)
