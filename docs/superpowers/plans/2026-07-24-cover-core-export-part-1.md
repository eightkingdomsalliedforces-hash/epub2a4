# Shared Cover Core and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canonical Python cover engine used by Android and desktop for metadata inspection, project JSON, spine and A4 geometry, local templates, preview rendering, PDF export, and editable DOCX export.

**Architecture:** Move the existing Python conversion package to one repository-level source tree and point Chaquopy at it rather than maintaining an Android-only copy. Add a focused `epub_a4_word.cover` package whose public service API accepts paths, primitive values, and UTF-8 JSON so Kotlin and PySide6 receive identical results.

**Tech Stack:** Python 3.13, dataclasses, Pillow 11.0.0, python-docx 1.1.2, lxml 5.3.0, pypdf 6.14.2, pytest; Chaquopy source sets; OOXML DrawingML/VML.

## Global Constraints

- Android remains API 24+ and arm64-v8a.
- The canonical package is `python/src/epub_a4_word`; no second committed copy may remain under `app/src/main/python/epub_a4_word`.
- `CoverProject.schema_version` is `1`.
- All dimensions and positions are stored as decimal millimetres.
- Cover order is `back | spine | front`.
- Supported trim sizes: A5 `148 × 210 mm`, A6 `105 × 148 mm`, 4×6 inch `101.6 × 152.4 mm`.
- Default bleed is `3 mm`, valid range `0..10 mm`.
- Automatic spine width is `ceil(page_count / 2) × paper_caliper_mm`.
- Default overlap is exactly `5 mm`.
- Never scale a finished cover to fit A4.
- PDF is the print reference and defaults to `300 DPI`; Android may explicitly request `200 DPI`.
- DOCX page size is exact A4 and principal text/image elements remain individually editable.
- Existing EPUB and DOCX conversion tests must remain green.

---

## Part 1: Tasks 1–3

### Task 1: Canonicalize the shared Python source tree

**Files:**
- Create: `pyproject.toml`
- Move: `app/src/main/python/epub_a4_word/` → `python/src/epub_a4_word/`
- Modify: `app/build.gradle.kts`
- Modify: `app/src/main/python/android_bridge.py`
- Modify: `.github/workflows/android.yml`
- Modify: `BUILDING.md`
- Modify: `scripts/verify_project.py`

**Interfaces:**
- Produces: importable package `epub_a4_word` from `python/src` on desktop and from Chaquopy on Android.
- Preserves the public functions `android_bridge.convert_file_json` and `android_bridge.probe`.

- [ ] **Step 1: Add a failing canonical-source test**

Create `python-tests/test_source_layout.py`:

```python
from pathlib import Path


def test_core_has_one_committed_source_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "python/src/epub_a4_word/__init__.py").is_file()
    assert not (root / "app/src/main/python/epub_a4_word").exists()


def test_android_bridge_imports_canonical_core() -> None:
    import android_bridge

    result = android_bridge.probe()
    assert result["python_core_version"]
    assert result["bridge_version"] == "1.0"
```

- [ ] **Step 2: Run the test and verify the old layout fails**

Run:

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest \
  python-tests/test_source_layout.py -q
```

Expected: FAIL because `python/src/epub_a4_word/__init__.py` does not exist and the Android-only package still exists.

- [ ] **Step 3: Move the package and configure both build systems**

Run:

```bash
mkdir -p python/src
git mv app/src/main/python/epub_a4_word python/src/epub_a4_word
```

Add to `app/build.gradle.kts` inside `chaquopy`:

```kotlin
sourceSets {
    getByName("main") {
        srcDir("../python/src")
    }
}
```

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "epub-a4-word"
version = "0.6.0"
requires-python = ">=3.13"
dependencies = [
  "beautifulsoup4==4.13.4",
  "lxml==5.3.0",
  "Pillow==11.0.0",
  "python-docx==1.1.2",
  "pypdf==6.14.2",
]

[project.optional-dependencies]
test = ["pytest>=8.3,<9"]

[tool.setuptools]
package-dir = {"" = "python/src"}

[tool.setuptools.packages.find]
where = ["python/src"]

[tool.pytest.ini_options]
testpaths = ["python-tests"]
pythonpath = ["python/src", "app/src/main/python"]
```

Add `install("pypdf==6.14.2")` to the existing Chaquopy `pip` block.

Update `.github/workflows/android.yml`, `BUILDING.md`, and `scripts/verify_project.py` so Python commands use:

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
PYTHONPATH=python/src:app/src/main/python python3.13 -m compileall -q \
  python/src app/src/main/python
```

- [ ] **Step 4: Run all existing Python tests**

Run:

```bash
python3.13 -m pip install -e '.[test]'
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
```

Expected: all pre-existing tests plus `test_source_layout.py` PASS.

- [ ] **Step 5: Commit the source-layout migration**

```bash
git add pyproject.toml python app app/build.gradle.kts python-tests \
  .github/workflows/android.yml BUILDING.md scripts/verify_project.py
git commit -m "refactor: share Python core across platforms"
```

---

### Task 2: Define the versioned CoverProject model and strict JSON codec

**Files:**
- Create: `python/src/epub_a4_word/cover/__init__.py`
- Create: `python/src/epub_a4_word/cover/models.py`
- Create: `python/src/epub_a4_word/cover/project_io.py`
- Create: `python-tests/cover/test_project_io.py`

**Interfaces:**
- Produces: `CoverProject`, `CoverElement`, `CoverMetadata`, `TrimSize`, `ExportSettings`.
- Produces: `dumps_project(project) -> str` and `loads_project(json_text) -> CoverProject`.
- Invariant: unknown schema versions, duplicate element IDs, invalid dimensions, invalid opacity, and missing image paths are rejected with `CoverValidationError`.

- [ ] **Step 1: Write failing round-trip and validation tests**

Create `python-tests/cover/test_project_io.py`:

```python
from pathlib import Path

import pytest

from epub_a4_word.cover.models import (
    CoverElement,
    CoverMetadata,
    CoverProject,
    ElementKind,
    ElementTransform,
    ImageMode,
    Region,
    TrimSize,
)
from epub_a4_word.cover.project_io import CoverValidationError, dumps_project, loads_project


def sample_project(tmp_path: Path) -> CoverProject:
    image = tmp_path / "cover.png"
    image.write_bytes(b"image-placeholder")
    return CoverProject(
        schema_version=1,
        source_file=str(tmp_path / "book.epub"),
        source_type="epub",
        metadata=CoverMetadata(title="範例書", author="作者"),
        trim_size=TrimSize(width_mm=105.0, height_mm=148.0),
        page_count=160,
        paper_caliper_mm=0.10,
        manual_spine_width_mm=None,
        bleed_mm=3.0,
        overlap_mm=5.0,
        image_mode=ImageMode.FRONT_ONLY,
        elements=(
            CoverElement(
                id="front-image",
                kind=ElementKind.IMAGE,
                region=Region.FRONT,
                transform=ElementTransform(0.0, 0.0, 105.0, 148.0),
                content={"path": str(image), "fit": "cover"},
            ),
        ),
    )


def test_project_round_trip_preserves_types(tmp_path: Path) -> None:
    restored = loads_project(dumps_project(sample_project(tmp_path)))
    assert restored.schema_version == 1
    assert restored.metadata.title == "範例書"
    assert restored.image_mode is ImageMode.FRONT_ONLY
    assert restored.elements[0].kind is ElementKind.IMAGE


def test_rejects_unknown_schema_version(tmp_path: Path) -> None:
    text = dumps_project(sample_project(tmp_path)).replace('"schema_version":1', '"schema_version":2')
    with pytest.raises(CoverValidationError, match="schema_version"):
        loads_project(text)


def test_rejects_duplicate_element_ids(tmp_path: Path) -> None:
    project = sample_project(tmp_path)
    duplicate = project.__class__(**{**project.__dict__, "elements": project.elements * 2})
    with pytest.raises(CoverValidationError, match="重複"):
        loads_project(dumps_project(duplicate))
```

- [ ] **Step 2: Run the test and verify missing modules fail**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_project_io.py -q
```

Expected: collection ERROR because `epub_a4_word.cover` does not exist.

- [ ] **Step 3: Implement immutable model types**

Create `python/src/epub_a4_word/cover/models.py` with these exact public definitions:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ImageMode(StrEnum):
    FRONT_ONLY = "front_only"
    FULL_SPREAD = "full_spread"


class ElementKind(StrEnum):
    IMAGE = "image"
    TEXT = "text"
    SHAPE = "shape"
    BARCODE_PLACEHOLDER = "barcode_placeholder"
    GUIDE = "guide"


class Region(StrEnum):
    BACK = "back"
    SPINE = "spine"
    FRONT = "front"
    SPREAD = "spread"


@dataclass(frozen=True)
class TrimSize:
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class CoverMetadata:
    title: str = ""
    author: str = ""
    description: str = ""
    isbn: str = ""
    publisher: str = ""
    language: str = ""
    page_count_is_estimate: bool = False
    embedded_images: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ElementTransform:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    rotation_deg: float = 0.0


@dataclass(frozen=True)
class CoverElement:
    id: str
    kind: ElementKind
    region: Region
    transform: ElementTransform
    z_index: int = 0
    opacity: float = 1.0
    content: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportSettings:
    dpi: int = 300
    show_crop_marks: bool = True
    show_assembly_marks: bool = True


@dataclass(frozen=True)
class CoverProject:
    schema_version: int
    source_file: str
    source_type: str
    metadata: CoverMetadata
    trim_size: TrimSize
    page_count: int
    paper_caliper_mm: float
    manual_spine_width_mm: float | None
    bleed_mm: float
    overlap_mm: float
    image_mode: ImageMode
    background: dict[str, Any] = field(default_factory=dict)
    elements: tuple[CoverElement, ...] = ()
    export_settings: ExportSettings = field(default_factory=ExportSettings)

    @property
    def elements_by_id(self) -> dict[str, CoverElement]:
        return {element.id: element for element in self.elements}
```

Export these names from `cover/__init__.py`.

- [ ] **Step 4: Implement deterministic JSON encoding and strict validation**

`project_io.py` must:

```python
class CoverValidationError(ValueError):
    """Raised when schema or physical cover values are invalid."""


def dumps_project(project: CoverProject) -> str:
    validate_project(project)
    return json.dumps(_to_json_value(project), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def loads_project(json_text: str) -> CoverProject:
    try:
        raw = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise CoverValidationError(f"封面專案 JSON 無效：{exc.msg}") from exc
    project = _project_from_dict(raw)
    validate_project(project)
    return project
```

Validation rules:

```python
if project.schema_version != 1: raise CoverValidationError("不支援的 schema_version")
if project.page_count < 1: raise CoverValidationError("page_count 必須大於 0")
if not 0.0 <= project.bleed_mm <= 10.0: raise CoverValidationError("bleed_mm 必須介於 0 與 10")
if project.overlap_mm != 5.0: raise CoverValidationError("第一版 overlap_mm 必須為 5")
if project.paper_caliper_mm <= 0: raise CoverValidationError("paper_caliper_mm 必須大於 0")
if project.manual_spine_width_mm is not None and project.manual_spine_width_mm <= 0: raise CoverValidationError("manual_spine_width_mm 必須大於 0")
```

For every element, require a non-empty unique ID, positive width/height, opacity in `0..1`, and an existing local file for `IMAGE` content key `path`.

- [ ] **Step 5: Run model tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_project_io.py -q
git add python/src/epub_a4_word/cover python-tests/cover/test_project_io.py
git commit -m "feat: add versioned cover project model"
```

Expected: all tests PASS.

---

### Task 3: Extract metadata from EPUB, DOCX, and PDF

**Files:**
- Create: `python/src/epub_a4_word/cover/metadata.py`
- Create: `python-tests/cover/test_metadata.py`
- Create: `python-tests/fixtures/cover/metadata.epub`
- Create: `python-tests/fixtures/cover/metadata.docx`
- Create: `python-tests/fixtures/cover/metadata.pdf`
- Modify: `python/src/epub_a4_word/epub.py`

**Interfaces:**
- Produces: `inspect_metadata(source_path: Path) -> CoverMetadataInspection`.
- `CoverMetadataInspection` fields: `source_type`, `metadata`, `fixed_page_count`, `warnings`.
- EPUB fixed page count is `None`; DOCX uses `docProps/app.xml/Pages` when present; PDF uses `len(PdfReader.pages)`.

- [ ] **Step 1: Add fixture builders and failing metadata assertions**

The test must assert:

```python
def test_epub_reads_opf_metadata_and_embedded_cover(fixtures_dir):
    result = inspect_metadata(fixtures_dir / "cover/metadata.epub")
    assert result.source_type == "epub"
    assert result.metadata.title == "測試 EPUB"
    assert result.metadata.author == "測試作者"
    assert result.metadata.description == "封底簡介"
    assert result.metadata.isbn == "9780000000001"
    assert result.fixed_page_count is None
    assert result.metadata.embedded_images[0]["role"] == "cover"


def test_docx_reads_core_properties_and_pages(fixtures_dir):
    result = inspect_metadata(fixtures_dir / "cover/metadata.docx")
    assert result.source_type == "docx"
    assert result.metadata.title == "測試 DOCX"
    assert result.metadata.author == "Word 作者"
    assert result.fixed_page_count == 12


def test_pdf_reads_document_info_and_actual_pages(fixtures_dir):
    result = inspect_metadata(fixtures_dir / "cover/metadata.pdf")
    assert result.source_type == "pdf"
    assert result.metadata.title == "測試 PDF"
    assert result.fixed_page_count == 3
```

Build the fixtures inside a pytest fixture with `zipfile`, `python-docx`, Pillow, and pypdf so no opaque binary file needs manual editing.

- [ ] **Step 2: Run targeted tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_metadata.py -q
```

Expected: collection ERROR because `cover.metadata` does not exist.

- [ ] **Step 3: Implement source dispatch and OOXML/PDF readers**

Use this public result type:

```python
@dataclass(frozen=True)
class CoverMetadataInspection:
    source_type: str
    metadata: CoverMetadata
    fixed_page_count: int | None
    warnings: tuple[str, ...] = ()
```

Dispatch by lowercase suffix:

```python
def inspect_metadata(source_path: Path | str) -> CoverMetadataInspection:
    source = Path(source_path)
    if not source.is_file():
        raise ValueError("找不到來源文件。")
    readers = {".epub": _inspect_epub, ".docx": _inspect_docx, ".pdf": _inspect_pdf}
    try:
        return readers[source.suffix.lower()](source)
    except KeyError as exc:
        raise ValueError("封面工具只支援 EPUB、DOCX 或 PDF。") from exc
```

Implementation requirements:

- EPUB: follow `META-INF/container.xml` to the OPF; read Dublin Core title, creator, description, identifier, publisher, language; identify cover via EPUB 3 `properties="cover-image"`, EPUB 2 `<meta name="cover">`, then image fallback.
- DOCX: read `docProps/core.xml`; read integer `Pages` from `docProps/app.xml`; missing or invalid pages returns `None` plus warning.
- PDF: use `PdfReader`; normalize leading slash metadata keys; encrypted PDF without an empty-password open raises `ValueError("無法讀取加密 PDF。")`.
- Embedded image entries contain only safe metadata: `id`, `href`, `media_type`, `role`, `width_px`, `height_px`; do not include bytes in JSON.

- [ ] **Step 4: Add EPUB page-count estimation for direct cover-tool entry**

Add:

```python
def estimate_epub_page_count(source_path: Path | str, settings: LayoutSettings) -> int:
    book = parse_epub(source_path)
    pages = paginate(book.blocks, settings, image_sizes={})
    return max(1, len(pages))
```

The caller must mark `CoverMetadata.page_count_is_estimate=True` when using this value. A conversion-completion flow passes the actual `mini_page_count` and does not call the estimator.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest \
  python-tests/cover/test_metadata.py python-tests/test_epub_parser.py -q
git add python/src/epub_a4_word/cover/metadata.py \
  python/src/epub_a4_word/epub.py python-tests/cover/test_metadata.py
git commit -m "feat: inspect cover metadata from supported documents"
```

Expected: all targeted tests PASS.

---
