from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "python/src/epub_a4_word_desktop/cover/controller.py",
    'from epub_a4_word.cover.isbn import normalize_isbn\n',
    'from epub_a4_word.cover.isbn import canonical_isbn13\n',
)
replace_once(
    "python/src/epub_a4_word_desktop/cover/controller.py",
    '    def apply_isbn(self, value: object) -> str:\n        isbn = normalize_isbn(value)\n        if not isbn:\n            raise ValueError("ISBN 必須是通過校驗的 ISBN-10 或 ISBN-13。")\n        project = self._require_project()\n        candidate = replace(project, metadata=replace(project.metadata, isbn=isbn))\n        active_template = str(candidate.background.get("active_template", ""))\n        if active_template == "publisher_back_matter":\n            candidate = apply_cover_template(candidate, active_template)\n        else:\n            updated: list[CoverElement] = []\n            for element in candidate.elements:\n                content = dict(element.content)\n                if element.kind is ElementKind.BARCODE_PLACEHOLDER:\n                    content["isbn"] = isbn\n                    content["text"] = isbn\n                elif element.id == "back-isbn-label":\n                    content["text"] = f"ISBN-13 {isbn}" if len(isbn) == 13 else f"ISBN-10 {isbn}"\n                updated.append(replace(element, content=content))\n            candidate = replace(candidate, elements=tuple(updated))\n        self.replace_project(dumps_project(candidate), label="套用 ISBN")\n        return isbn\n',
    '    def apply_isbn(self, value: object) -> str:\n        isbn = canonical_isbn13(value)\n        if not isbn:\n            raise ValueError("ISBN 必須是通過校驗的 ISBN-10 或 ISBN-13。")\n        project = self._require_project()\n        candidate = replace(project, metadata=replace(project.metadata, isbn=isbn))\n        active_template = str(candidate.background.get("active_template", ""))\n        if active_template == "publisher_back_matter":\n            generated_project = apply_cover_template(candidate, active_template)\n            generated = generated_project.elements_by_id\n            sync_ids = ("back-isbn-label", "back-isbn-code")\n            existing_ids = {element.id for element in candidate.elements}\n            updated: list[CoverElement] = []\n            for element in candidate.elements:\n                replacement_element = generated.get(element.id)\n                if element.id in sync_ids and replacement_element is not None:\n                    updated.append(\n                        replace(\n                            element,\n                            kind=replacement_element.kind,\n                            region=replacement_element.region,\n                            content=dict(replacement_element.content),\n                        )\n                    )\n                else:\n                    updated.append(element)\n            for element_id in sync_ids:\n                if element_id not in existing_ids and element_id in generated:\n                    updated.append(generated[element_id])\n            candidate = replace(\n                candidate,\n                background=generated_project.background,\n                elements=tuple(updated),\n            )\n        else:\n            updated = []\n            for element in candidate.elements:\n                content = dict(element.content)\n                if element.kind is ElementKind.BARCODE_PLACEHOLDER:\n                    content["isbn"] = isbn\n                    content["text"] = isbn\n                elif element.id == "back-isbn-label":\n                    content["text"] = f"ISBN-13 {isbn}"\n                updated.append(replace(element, content=content))\n            candidate = replace(candidate, elements=tuple(updated))\n        self.replace_project(dumps_project(candidate), label="套用 ISBN")\n        return isbn\n',
)
replace_once(
    "python/src/epub_a4_word_desktop/cover/items.py",
    'from epub_a4_word.cover.models import CoverElement\n',
    'from epub_a4_word.cover.isbn import (\n    canonical_isbn13,\n    encode_ean13_modules,\n    encode_ean_addon_modules,\n)\nfrom epub_a4_word.cover.models import CoverElement\n',
)
replace_once(
    "python/src/epub_a4_word_desktop/cover/items.py",
    '\n\nclass CoverTextItem(CoverElementItem):\n',
    '\n\nclass CoverBarcodeItem(CoverElementItem):\n    """Editable EAN-13 barcode element rendered directly on the scene."""\n\n    def __init__(self, element: CoverElement) -> None:\n        super().__init__(element)\n        self._content = dict(element.content)\n\n    def paint(\n        self,\n        painter: QPainter,\n        option: QStyleOptionGraphicsItem,\n        widget: QWidget | None = None,\n    ) -> None:\n        del option, widget\n        target = self.boundingRect()\n        isbn = canonical_isbn13(\n            self._content.get("isbn", self._content.get("text", ""))\n        )\n        if isbn:\n            modules = encode_ean13_modules(isbn)\n            addon_modules = encode_ean_addon_modules(self._content.get("addon", ""))\n            quiet_modules = 9\n            separator_modules = 8 if addon_modules else 0\n            total_modules = (\n                quiet_modules * 2\n                + len(modules)\n                + separator_modules\n                + len(addon_modules)\n            )\n            module_width = target.width() / max(1, total_modules)\n            bar_height = target.height() * 0.78\n            x = target.left() + quiet_modules * module_width\n            painter.save()\n            painter.setPen(Qt.PenStyle.NoPen)\n            painter.setBrush(QColor("black"))\n            for bit in modules:\n                if bit == "1":\n                    painter.drawRect(\n                        QRectF(x, target.top(), module_width, bar_height)\n                    )\n                x += module_width\n            if addon_modules:\n                x += separator_modules * module_width\n                addon_top = target.top() + bar_height * 0.12\n                for bit in addon_modules:\n                    if bit == "1":\n                        painter.drawRect(\n                            QRectF(\n                                x,\n                                addon_top,\n                                module_width,\n                                target.top() + bar_height - addon_top,\n                            )\n                        )\n                    x += module_width\n            font = QFont("Sans Serif")\n            font.setPointSizeF(max(3.0, min(10.0, target.height() * 0.14)))\n            painter.setFont(font)\n            painter.setPen(QColor("black"))\n            painter.drawText(\n                QRectF(\n                    target.left(),\n                    target.top() + bar_height,\n                    target.width(),\n                    target.height() - bar_height,\n                ),\n                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,\n                " ".join((isbn[:3], isbn[3:])),\n            )\n            painter.restore()\n        self._paint_selection_handles(painter)\n\n\nclass CoverTextItem(CoverElementItem):\n',
)
replace_once(
    "python/src/epub_a4_word_desktop/cover/canvas.py",
    'from .items import CoverImageItem, CoverTextItem\n',
    'from .items import CoverBarcodeItem, CoverImageItem, CoverTextItem\n',
)
replace_once(
    "python/src/epub_a4_word_desktop/cover/canvas.py",
    '        self.items_by_id: dict[str, CoverImageItem | CoverTextItem] = {}\n',
    '        self.items_by_id: dict[str, CoverBarcodeItem | CoverImageItem | CoverTextItem] = {}\n',
)
replace_once(
    "python/src/epub_a4_word_desktop/cover/canvas.py",
    '        for element in sorted(project.elements, key=lambda item: item.z_index):\n            item: CoverImageItem | CoverTextItem | None\n            if element.kind is ElementKind.IMAGE:\n                item = CoverImageItem(element)\n            elif element.kind is ElementKind.TEXT:\n                item = CoverTextItem(element)\n            else:\n                item = None\n',
    '        for element in sorted(project.elements, key=lambda item: item.z_index):\n            item: CoverBarcodeItem | CoverImageItem | CoverTextItem | None\n            if element.kind is ElementKind.IMAGE:\n                item = CoverImageItem(element)\n            elif element.kind is ElementKind.TEXT:\n                item = CoverTextItem(element)\n            elif element.kind is ElementKind.BARCODE_PLACEHOLDER:\n                item = CoverBarcodeItem(element)\n            else:\n                item = None\n',
)
print("applied publisher interaction fixes")
