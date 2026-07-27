from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


controller_path = Path("python/src/epub_a4_word_desktop/cover/controller.py")
old_controller = '''        project = self._require_project()
        candidate = replace(project, metadata=replace(project.metadata, isbn=isbn))
        active_template = str(candidate.background.get("active_template", ""))
        if active_template == "publisher_back_matter":
            generated_project = apply_cover_template(candidate, active_template)
            generated = generated_project.elements_by_id
            sync_ids = ("back-isbn-label", "back-isbn-code")
            existing_ids = {element.id for element in candidate.elements}
            updated: list[CoverElement] = []
            for element in candidate.elements:
                generated_element = generated.get(element.id)
                if element.id in sync_ids and generated_element is not None:
                    updated.append(
                        replace(
                            element,
                            kind=generated_element.kind,
                            region=generated_element.region,
                            content=dict(generated_element.content),
                        )
                    )
                else:
                    updated.append(element)
            for element_id in sync_ids:
                if element_id not in existing_ids and element_id in generated:
                    updated.append(generated[element_id])
            candidate = replace(
                candidate,
                background=generated_project.background,
                elements=tuple(updated),
            )
        else:
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
'''
new_controller = '''        project = self._require_project()
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
'''
replace_once(controller_path, old_controller, new_controller)

replace_once(
    Path("python/src/epub_a4_word_desktop/cover/setup_panel.py"),
    '            "publisher_back_matter_with_spine",\n'
    '        )\n'
    '        self.create_button = QPushButton',
    '            "publisher_back_matter",\n'
    '        )\n'
    '        self.create_button = QPushButton',
)

replace_once(
    Path("python/src/epub_a4_word_desktop/pages/cover_page.py"),
    '("出版社封底＋直式書脊", "publisher_back_matter_with_spine"),\n',
    '("出版社封底＋直式書脊", "publisher_back_matter"),\n',
)

replace_once(
    Path("python/src/epub_a4_word_desktop/cover/canvas.py"),
    '        scene = self.scene()\n'
    '        scene.clear()\n'
    '        self.items_by_id.clear()\n'
    '        self.group_members_by_element.clear()\n',
    '        scene = self.scene()\n'
    '        self._syncing_group_selection = True\n'
    '        try:\n'
    '            self.items_by_id.clear()\n'
    '            self.group_members_by_element.clear()\n'
    '            scene.clear()\n'
    '        finally:\n'
    '            self._syncing_group_selection = False\n',
)

replace_once(
    Path("desktop/tests/test_publisher_workflow.py"),
    "def test_publisher_logo_image_uses_contain_without_cropping(tmp_path: Path) -> None:\n",
    "def test_publisher_logo_image_uses_contain_without_cropping(qtbot, tmp_path: Path) -> None:\n",
)
