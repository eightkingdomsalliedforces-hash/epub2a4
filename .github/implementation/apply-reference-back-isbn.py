from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "python/src/epub_a4_word/cover/templates.py",
    '''def _publisher_logo_rect(layout: CoverLayout) -> RectMm:\n    safe = layout.back_safe_rect\n    width = safe.width_mm * 0.58\n    height = safe.height_mm * 0.34\n    return RectMm(\n        safe.x_mm + (safe.width_mm - width) / 2.0,\n        safe.y_mm + safe.height_mm * 0.38,\n        width,\n        height,\n    )\n''',
    '''def _publisher_logo_rect(layout: CoverLayout) -> RectMm:\n    safe = layout.back_safe_rect\n    return RectMm(\n        safe.x_mm + safe.width_mm * 0.26,\n        safe.y_mm + safe.height_mm * 0.34,\n        safe.width_mm * 0.48,\n        safe.height_mm * 0.36,\n    )\n''',
)

replace_once(
    "python/src/epub_a4_word/cover/templates.py",
    '''        label_rect = RectMm(\n            safe.x_mm,\n            safe.y_mm,\n            safe.width_mm * 0.55,\n            max(5.0, safe.height_mm * 0.035),\n        )\n        barcode_rect = RectMm(\n            safe.x_mm,\n            label_rect.bottom_mm + 1.5,\n            safe.width_mm * 0.55,\n            max(24.0, safe.height_mm * 0.16),\n        )\n''',
    '''        label_rect = RectMm(\n            safe.x_mm + safe.width_mm * 0.10,\n            safe.y_mm + safe.height_mm * 0.06,\n            safe.width_mm * 0.36,\n            safe.height_mm * 0.035,\n        )\n        barcode_rect = RectMm(\n            label_rect.x_mm,\n            safe.y_mm + safe.height_mm * 0.105,\n            safe.width_mm * 0.36,\n            safe.height_mm * 0.105,\n        )\n''',
)

replace_once(
    "python/src/epub_a4_word/cover/templates.py",
    '                f"ISBN-13 {isbn}",\n',
    '                f"ISBN {isbn}",\n',
)

replace_once(
    "python/src/epub_a4_word/cover/templates.py",
    '''        info_rect = RectMm(\n            safe.x_mm + safe.width_mm * 0.61,\n            safe.y_mm,\n            safe.width_mm * 0.39,\n            max(30.0, safe.height_mm * 0.20),\n        )\n''',
    '''        info_rect = RectMm(\n            safe.x_mm + safe.width_mm * 0.48,\n            safe.y_mm + safe.height_mm * 0.06,\n            safe.width_mm * 0.30,\n            safe.height_mm * 0.14,\n        )\n''',
)

replace_once(
    "python/src/epub_a4_word/cover/templates.py",
    '                align="right",\n',
    '                align="left",\n',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/controller.py",
    '''    @staticmethod\n    def _target_rect(project: CoverProject, region: Region):\n        layout = calculate_layout(project)\n        if region is Region.BACK and str(project.background.get("active_template", "")) == "publisher_back_matter":\n            slot = project.background.get("publisher_logo_slot")\n''',
    '''    @staticmethod\n    def _uses_publisher_logo_slot(project: CoverProject, region: Region) -> bool:\n        return (\n            region is Region.BACK\n            and str(project.background.get("active_template", ""))\n            == "publisher_back_matter"\n            and isinstance(project.background.get("publisher_logo_slot"), Mapping)\n        )\n\n    @staticmethod\n    def _target_rect(project: CoverProject, region: Region):\n        layout = calculate_layout(project)\n        if CoverController._uses_publisher_logo_slot(project, region):\n            slot = project.background.get("publisher_logo_slot")\n''',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/controller.py",
    '            "fit": "cover",\n',
    '            "fit": "contain" if self._uses_publisher_logo_slot(project, region) else "cover",\n',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/controller.py",
    '                    content["text"] = f"ISBN-13 {isbn}"\n',
    '                    content["text"] = f"ISBN {isbn}"\n',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    '''from epub_a4_word.cover.project_io import loads_project\n''',
    '''from epub_a4_word.cover.isbn import isbn13_from_isbn10\nfrom epub_a4_word.cover.project_io import loads_project\n''',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    '''_CATEGORY_LABELS = {\n    CandidateCategory.FRONT: "正面",\n    CandidateCategory.BACK: "背面",\n    CandidateCategory.SPINE: "書脊",\n    CandidateCategory.FULL_SPREAD: "完整書衣",\n    CandidateCategory.REFERENCE_PHOTO: "實拍參考",\n    CandidateCategory.UNKNOWN: "無法判定",\n}\n\n\nclass CandidateCard(QFrame):\n''',
    '''_CATEGORY_LABELS = {\n    CandidateCategory.FRONT: "正面",\n    CandidateCategory.BACK: "背面",\n    CandidateCategory.SPINE: "書脊",\n    CandidateCategory.FULL_SPREAD: "完整書衣",\n    CandidateCategory.REFERENCE_PHOTO: "實拍參考",\n    CandidateCategory.UNKNOWN: "無法判定",\n}\n\n\ndef candidate_isbn10(candidate: SearchCandidate) -> str:\n    return next(\n        (\n            value\n            for value in candidate.isbns\n            if len(value) == 10 and isbn13_from_isbn10(value) == candidate.isbn\n        ),\n        "",\n    )\n\n\ndef candidate_isbn_summary(candidate: SearchCandidate) -> str:\n    if not candidate.isbn:\n        return ""\n    lines = [f"建議 ISBN-13：{candidate.isbn}"]\n    isbn10 = candidate_isbn10(candidate)\n    if isbn10:\n        lines.append(f"對應 ISBN-10：{isbn10}（同一版本對應碼）")\n    return "\\n".join(lines)\n\n\ndef candidate_edition_summary(candidate: SearchCandidate) -> str:\n    lines: list[str] = []\n    if candidate.publisher.strip():\n        lines.append(f"出版社：{candidate.publisher.strip()}")\n    if candidate.language.strip():\n        lines.append(f"語言：{candidate.language.strip()}")\n    if candidate.classification_reasons:\n        reasons = "、".join(\n            reason.strip()\n            for reason in candidate.classification_reasons\n            if reason.strip()\n        )\n        if reasons:\n            lines.append(f"判定：{reasons}")\n    return "\\n".join(lines)\n\n\nclass CandidateCard(QFrame):\n''',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    '''        isbn_lines = [\n            f"ISBN-{len(value)} {value}"\n            for value in candidate.isbns\n        ]\n        self.isbn_label = QLabel("\\n".join(isbn_lines), self)\n        self.isbn_label.setWordWrap(True)\n        self.isbn_label.setVisible(bool(isbn_lines))\n''',
    '''        isbn_summary = candidate_isbn_summary(candidate)\n        self.isbn_label = QLabel(isbn_summary, self)\n        self.isbn_label.setWordWrap(True)\n        self.isbn_label.setVisible(bool(isbn_summary))\n        edition_summary = candidate_edition_summary(candidate)\n        self.edition_label = QLabel(edition_summary, self)\n        self.edition_label.setWordWrap(True)\n        self.edition_label.setVisible(bool(edition_summary))\n''',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    '''        layout.addWidget(resolution_label)\n        layout.addWidget(self.isbn_label)\n        layout.addWidget(rights)\n''',
    '''        layout.addWidget(resolution_label)\n        layout.addWidget(self.isbn_label)\n        layout.addWidget(self.edition_label)\n        layout.addWidget(rights)\n''',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    '''        isbns = getattr(response, "resolved_isbns", ())\n        confirmed_text = "、".join(\n            item.value\n            for item in aliases\n            if item.confidence != "medium" or alias_key(item) in self.accepted_aliases\n        )\n        details = []\n        if confirmed_text:\n            details.append("可使用名稱：" + confirmed_text)\n        if isbns:\n            details.append("解析 ISBN：" + "、".join(isbns))\n        self.resolution_label.setText("；".join(details))\n''',
    '''        confirmed_text = "、".join(\n            item.value\n            for item in aliases\n            if item.confidence != "medium" or alias_key(item) in self.accepted_aliases\n        )\n        details = []\n        if confirmed_text:\n            details.append("可使用名稱：" + confirmed_text)\n        if self.candidates:\n            details.append(f"找到 {len(self.candidates)} 個候選版本")\n        self.resolution_label.setText("；".join(details))\n''',
)

replace_once(
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    '''            labels = [\n                f"{_CATEGORY_LABELS[CandidateCategory(key)]}：{value.title or urlsplit(value.source_page).netloc}"\n                for key, value in self.selected.items()\n            ]\n            self.selection_label.setText("\\n".join(labels))\n''',
    '''            labels = [\n                f"{_CATEGORY_LABELS[CandidateCategory(key)]}：{value.title or urlsplit(value.source_page).netloc}"\n                for key, value in self.selected.items()\n            ]\n            recommended = next(\n                (candidate for candidate in self.selected.values() if candidate.isbn),\n                None,\n            )\n            if recommended is not None:\n                labels.append(candidate_isbn_summary(recommended))\n            self.selection_label.setText("\\n".join(labels))\n''',
)

(ROOT / ".github/implementation/apply-reference-back-isbn.py").unlink()
(ROOT / ".github/workflows/apply-reference-back-isbn.yml").unlink()
