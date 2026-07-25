# Free Cover Sources, Cross-Language Lookup, EPUB Back Cover, Content-Only Output, and Single-Page DOCX Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a completely free cover-search pipeline with cross-language title resolution, extract EPUB front and back covers, default EPUB conversion to body-only output, and eliminate Microsoft Word blank-page regressions in A5 and 4×6 single-page DOCX output.

**Architecture:** Add one shared EPUB structure inspector that owns OPF, manifest, spine, guide, and landmark analysis and returns confidence-scored front/back-cover roles. Conversion filtering, cover metadata, and cover-project initialization consume that result separately. Cover lookup becomes an ordered query pipeline: normalized EPUB metadata → optional Google Books bibliographic bridge → Wikidata aliases → enabled Google Books, Open Library, and Gutendex providers, with per-provider failure isolation and a local confirmed-alias cache.

**Tech Stack:** Python 3.11+, BeautifulSoup/lxml, python-docx and direct OOXML, PySide6, Pillow, the existing `JsonHttpClient`, pytest/pytest-qt, LibreOffice plus `pdfinfo`, GitHub Actions, and PyInstaller.

## Global Constraints

- New lookup services must be free. Do not add ISBNdb, paid APIs, Z-Library, or unstable book-site scraping.
- Google Books requires only `api_key`; Search Engine ID and Google Custom Search are not part of the new workflow.
- Open Library and Gutendex are independently switchable and need no key.
- Wikidata resolves multilingual names and identifiers only; it does not return cover candidates.
- Network requests may send title, author, ISBN, language, and query parameters only. Never upload EPUB, DOCX, PDF, body text, or local image bytes.
- `content_only` defaults to `true` for EPUB conversion. DOCX reflow is unaffected.
- Only high-confidence cover pages are removed automatically. A medium-confidence back cover requires explicit confirmation.
- EPUB front/back images stay as separate editable source files and elements. Do not generate replacement images.
- New source-cover projects must not automatically add title, description, publisher, spine text, or barcode elements.
- A5 must resolve to 148.0 × 210.0 mm; 4×6 must resolve to 101.6 × 152.4 mm, within OOXML twip rounding tolerance.
- N A5, 4×6, or B6-on-A5 content pages must produce N physical pages with no leading, interstitial, or trailing blank page.
- Existing project JSON and credential files remain readable.
- Verify shared and desktop tests on Windows, macOS, and Ubuntu, plus Windows portable packaging and packaged-EXE smoke.

---

### Task 1: Reproduce and remove A5/4×6 single-page OOXML blank-page risk

**Files:**
- Modify: `python/src/epub_a4_word/docx_writer.py:249-368`
- Modify: `python-tests/core/test_docx_writer.py:226-300`
- Create: `python-tests/test_single_page_blank_page_regression.py`
- Modify: `python-tests/core/test_integration.py:56-74`

**Interfaces:**
- Consumes: `write_docx(...)`.
- Produces: A5, 4×6, and B6-on-A5 use one top-level table with one exact-height, non-splittable row per physical page.

- [ ] **Step 1: Write failing OOXML structure tests**

```python
@pytest.mark.parametrize("mode", ["single_a5", "single_4x6", "b6_on_a5"])
def test_single_page_modes_have_no_prefix_paragraphs(tmp_path, mode):
    output = tmp_path / f"{mode}.docx"
    write_docx(
        [_page(1), _page(2), _page(3)], output,
        resources={}, media_types={},
        settings=LayoutSettings(imposition_mode=mode),
        imposition_mode=mode,
    )
    with ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{{{W_NS}}}body")
    assert [etree.QName(child).localname for child in body] == ["tbl", "sectPr"]
    assert int(root.xpath("count(.//w:body/w:tbl/w:tr)", namespaces={"w": W_NS})) == 3
```

- [ ] **Step 2: Run the regression test**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/test_single_page_blank_page_regression.py \
  python-tests/test_b6_blank_page_regression.py
```

Expected before implementation: A5 and 4×6 fail with `p, tbl, p, tbl...`; B6 passes.

- [ ] **Step 3: Generalize the B6 writer path**

```python
_SINGLE_PAGE_TABLE_MODES = frozenset({"single_a5", "single_4x6", "b6_on_a5"})
```

Extract the current B6 multirow-table code into `_write_single_page_rows(...)` and call it for all three modes. Keep prefix paragraphs only for `signature16` and `four_up`.

- [ ] **Step 4: Verify rendered page count and size**

Add a LibreOffice/`pdfinfo` test for three pages per mode. Require A5/B6 PDF page size near 420 × 595 pt and 4×6 near 288 × 432 pt. Retain direct python-docx assertions for 14.8 × 21.0 cm and 10.16 × 15.24 cm.

- [ ] **Step 5: Run focused tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/test_single_page_blank_page_regression.py \
  python-tests/test_b6_blank_page_regression.py \
  python-tests/core/test_docx_writer.py \
  python-tests/core/test_integration.py
```

- [ ] **Step 6: Commit**

```bash
git add python/src/epub_a4_word/docx_writer.py \
  python-tests/test_single_page_blank_page_regression.py \
  python-tests/core/test_docx_writer.py python-tests/core/test_integration.py
git commit -m "fix: prevent blank pages in single-page docx modes"
```

---

### Task 2: Add a shared EPUB structure and cover-role inspector

**Files:**
- Create: `python/src/epub_a4_word/epub_structure.py`
- Create: `python-tests/core/test_epub_structure.py`
- Modify: `python/src/epub_a4_word/cover/metadata.py:43-139`
- Modify: `python/src/epub_a4_word/epub.py:209-283`

**Interfaces:**

```python
class CoverConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    NONE = "none"

@dataclass(frozen=True)
class EpubCoverDetection:
    front_resource: str | None
    front_page: str | None
    back_resource: str | None
    back_page: str | None
    back_confidence: CoverConfidence
    back_reasons: tuple[str, ...]

@dataclass(frozen=True)
class EpubStructure:
    opf_path: str
    manifest: dict[str, EpubManifestItem]
    spine_ids: tuple[str, ...]
    spine_documents: tuple[str, ...]
    detection: EpubCoverDetection


def inspect_epub_structure(path: Path | str) -> EpubStructure: ...
```

- [ ] **Step 1: Write synthetic EPUB tests**

Add tests for EPUB 3 `cover-image`, EPUB 2 `meta name="cover"`, guide/landmark back cover, a filename-marked final pure-image page, and a normal final illustration that must not be auto-classified.

- [ ] **Step 2: Run tests and confirm import failure**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q python-tests/core/test_epub_structure.py
```

- [ ] **Step 3: Implement package parsing and confidence rules**

Resolve container/OPF paths safely; collect manifest and spine; inspect guide and landmarks; parse pure-image wrapper pages. Front priority: `cover-image` → EPUB 2 cover metadata → guide/landmark → first named pure-image spine page. Back priority: explicit semantics → named final pure-image page → size-matched final pure-image page as medium confidence only.

- [ ] **Step 4: Reuse the inspector**

`metadata.py` assigns embedded-image roles `front_cover`, `back_cover`, `back_cover_candidate`, or `image`. `epub.py` uses `structure.spine_documents` instead of rebuilding the spine independently.

- [ ] **Step 5: Run parser and metadata tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/core/test_epub_structure.py \
  python-tests/core/test_epub_parser.py \
  python-tests/cover/test_metadata.py \
  python-tests/cover/test_user_reported_cover_regressions.py
```

- [ ] **Step 6: Commit**

```bash
git add python/src/epub_a4_word/epub_structure.py \
  python/src/epub_a4_word/epub.py python/src/epub_a4_word/cover/metadata.py \
  python-tests/core/test_epub_structure.py
git commit -m "feat: detect epub front and back cover resources"
```

---

### Task 3: Implement default body-only EPUB conversion

**Files:**
- Modify: `python/src/epub_a4_word/epub.py`
- Modify: `python/src/epub_a4_word/converter.py:52-137`
- Modify: `python/src/epub_a4_word/cover/service.py:122-152,235-260`
- Modify: `python-tests/core/test_epub_parser.py`
- Modify: `python-tests/core/test_integration.py`

**Interfaces:**

```python
def parse_epub(path, *, content_only: bool = True,
               confirmed_back_cover_page: str | None = None) -> ParsedBook: ...

def estimate_epub_page_count(source_path, settings, *, content_only: bool = True,
                             confirmed_back_cover_page: str | None = None) -> int: ...

def convert_input(..., *, content_only: bool = True,
                  confirmed_back_cover_page: str | None = None) -> ConversionResult: ...
```

- [ ] **Step 1: Write true/false and confidence tests**

Test high-confidence front/back exclusion, `content_only=False` preserving original spine order, medium back candidates remaining until confirmed, and no leading/double `PageBreakBlock` after filtering.

- [ ] **Step 2: Run the tests and record failures**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/core/test_epub_parser.py -k "content_only or back_cover"
```

- [ ] **Step 3: Filter spine documents before parsing**

Build an exclusion set from detected front page, high-confidence back page, and optional confirmed back page. Insert page breaks only between retained documents.

- [ ] **Step 4: Thread the setting through conversion and estimates**

Pass the setting through `convert_epub`, `convert_input`, and cover page-count estimation. Default estimates exclude confirmed covers.

- [ ] **Step 5: Run integration tests and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/core/test_epub_parser.py python-tests/core/test_integration.py \
  python-tests/cover/test_round2_shared.py

git add python/src/epub_a4_word/epub.py python/src/epub_a4_word/converter.py \
  python/src/epub_a4_word/cover/service.py python-tests/core \
  python-tests/cover/test_round2_shared.py
git commit -m "feat: default epub conversion to body-only content"
```

---

### Task 4: Add the body-only option to desktop conversion

**Files:**
- Modify: `python/src/epub_a4_word_desktop/conversion/models.py`
- Modify: `python/src/epub_a4_word_desktop/conversion/controller.py`
- Modify: `python/src/epub_a4_word_desktop/conversion/legacy_adapter.py`
- Modify: `python/src/epub_a4_word_desktop/pages/converter_page.py`
- Modify: `desktop/tests/test_converter_page.py`
- Modify: `desktop/tests/test_conversion_controller.py`
- Modify: `desktop/tests/test_legacy_gui_logic.py`

**Interfaces:**
- Add `content_only: bool = True` to desktop conversion requests.
- `ConversionWorker` passes it to `convert_input`.

- [ ] **Step 1: Write desktop tests**

Test that the checkbox is checked on first construction, enabled for EPUB, disabled with an explanatory tooltip for DOCX, and included in the conversion request.

- [ ] **Step 2: Run tests to verify failure**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q \
  desktop/tests/test_converter_page.py desktop/tests/test_conversion_controller.py \
  desktop/tests/test_legacy_gui_logic.py
```

- [ ] **Step 3: Add the checkbox**

```python
self.content_only = QCheckBox("只輸出內文，不含封面與封底", self)
self.content_only.setChecked(True)
self.content_only.setToolTip("只排除已明確辨識或由你確認的 EPUB 封面頁；不會刪除正文插圖。")
```

- [ ] **Step 4: Pass the value to `convert_input`**

```python
convert_input(..., self._progress, content_only=self.request.content_only)
```

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q \
  desktop/tests/test_converter_page.py desktop/tests/test_conversion_controller.py \
  desktop/tests/test_legacy_gui_logic.py

git add python/src/epub_a4_word_desktop/conversion \
  python/src/epub_a4_word_desktop/pages/converter_page.py desktop/tests
git commit -m "feat: add body-only epub conversion option"
```

---

### Task 5: Initialize cover projects with separate EPUB front and back images

**Files:**
- Modify: `python/src/epub_a4_word/cover/models.py`
- Modify: `python/src/epub_a4_word/cover/service.py:156-317`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Modify: `python-tests/cover/test_service.py`
- Modify: `python-tests/cover/test_round2_shared.py`
- Modify: `desktop/tests/test_round2_desktop.py`

**Interfaces:**
- Add `ImageMode.SEPARATE_COVERS = "separate_covers"`.
- Preserve front ID `source-cover-image`; add `source-back-cover-image` in `Region.BACK`.

- [ ] **Step 1: Write failing project tests**

Assert an EPUB with explicit front/back creates two image elements, separate asset paths, empty spine, and no text/barcode elements. Test front-only and medium-candidate cases.

- [ ] **Step 2: Run tests and confirm only front extraction exists**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/cover/test_service.py python-tests/cover/test_round2_shared.py
```

- [ ] **Step 3: Replace `_extract_epub_cover` with role-aware extraction**

Extract only `front_cover` and high-confidence `back_cover`; never auto-use `back_cover_candidate`.

- [ ] **Step 4: Create separate region elements**

If both assets exist and full-spread mode is not explicitly selected, create front/back elements with `fit="cover"` and set `SEPARATE_COVERS`. Keep compatibility for front-only and full-spread projects.

- [ ] **Step 5: Update setup status and run tests**

Display `已找到正面封面`, `已找到封底`, or `可能的封底需確認`. Then run shared and desktop cover tests.

- [ ] **Step 6: Commit**

```bash
git add python/src/epub_a4_word/cover/models.py \
  python/src/epub_a4_word/cover/service.py \
  python/src/epub_a4_word_desktop/cover/setup_panel.py \
  python-tests/cover desktop/tests
git commit -m "feat: use embedded epub front and back covers"
```

---

### Task 6: Add normalized book identity and ordered query planning

**Files:**
- Create: `python/src/epub_a4_word/cover/search/query_plan.py`
- Create: `python-tests/cover/test_query_plan.py`
- Modify: `python/src/epub_a4_word/cover/search/models.py`
- Modify: `python/src/epub_a4_word/cover/search/__init__.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class BookIdentity:
    original_title: str
    normalized_title: str
    author: str
    normalized_author: str
    volume: str
    isbn: str
    language: str

@dataclass(frozen=True)
class ResolvedAlias:
    value: str
    language: str | None
    source: str
    confidence: str
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class QueryItem:
    kind: str
    value: str
    author: str
    language: str
    confidence: str
    source: str
    reason: str

@dataclass(frozen=True)
class QueryPlan:
    identity: BookIdentity
    items: tuple[QueryItem, ...]
```

- [ ] **Step 1: Write normalization tests**

Cover `魔法禁書目錄 01（繁體中文版）`, `Vol. 2`, and Roman-numeral volume formats. Assert original metadata is retained, format labels are removed conservatively, volume is separated, UUIDs do not become ISBNs, and order is ISBN → manual alias → original title → normalized title.

- [ ] **Step 2: Run tests and confirm module absence**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q python-tests/cover/test_query_plan.py
```

- [ ] **Step 3: Implement conservative normalization and deduplication**

Do not freely translate titles. Normalize Unicode, whitespace, full-width numbers, Roman numerals, known edition labels, and common site/file suffixes. Deduplicate query items while preserving priority.

- [ ] **Step 4: Run tests and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/cover/test_query_plan.py \
  python-tests/cover/test_user_reported_cover_regressions.py

git add python/src/epub_a4_word/cover/search \
  python-tests/cover/test_query_plan.py
git commit -m "feat: normalize book metadata and build query plans"
```

---

### Task 7: Make Google Books credentials API-key-only and preserve old files

**Files:**
- Modify: `python/src/epub_a4_word/cover/search/models.py`
- Modify: `python/src/epub_a4_word_desktop/settings/credentials.py`
- Modify: `python/src/epub_a4_word_desktop/cover/credential_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/cover/search_controller.py`
- Modify: `desktop/tests/test_round2_desktop.py`
- Modify: `desktop/tests/test_cover_controller.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ProviderCredential:
    api_key: str
    search_engine_id: str = ""  # legacy read compatibility only

    @property
    def complete(self) -> bool:
        return bool(self.api_key.strip())
```

- [ ] **Step 1: Write migration and dialog tests**

Test API-key-only completeness, old JSON read compatibility, new JSON containing only `api_key`, keyring load with only `api-key`, and absence of the Search Engine ID field in the dialog.

- [ ] **Step 2: Run tests and verify current two-field validation fails**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q \
  desktop/tests/test_round2_desktop.py desktop/tests/test_cover_controller.py
```

- [ ] **Step 3: Update stores and dialog**

Use new service name `EPUB2A4 Google Books`, fall back to the legacy API-key entry when loading, and clear both names. Accept but ignore legacy `search_engine_id` JSON. Set dialog title to `Google Books API 設定` and validation to `請填入 Google Books API Key。`.

- [ ] **Step 4: Remove Google Custom Search from the active workflow**

Do not instantiate or call `GeneralCoverSearch`/`GoogleCustomSearchProvider` in the new controller path. Legacy modules may remain importable.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q \
  desktop/tests/test_round2_desktop.py desktop/tests/test_cover_controller.py \
  desktop/tests/test_windows_portable_packaging.py

git add python/src/epub_a4_word/cover/search/models.py \
  python/src/epub_a4_word_desktop/settings/credentials.py \
  python/src/epub_a4_word_desktop/cover/credential_dialog.py \
  python/src/epub_a4_word_desktop/cover/search_controller.py desktop/tests
git commit -m "fix: require only a Google Books API key"
```

---

### Task 8: Add Wikidata multilingual alias resolution

**Files:**
- Create: `python/src/epub_a4_word/cover/search/wikidata.py`
- Create: `python-tests/cover/test_wikidata.py`
- Modify: `python/src/epub_a4_word/cover/search/__init__.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class AliasResolution:
    aliases: tuple[ResolvedAlias, ...]
    isbns: tuple[str, ...]
    warnings: tuple[str, ...] = ()

class WikidataAliasResolver:
    def __init__(self, http: JsonHttpClient): ...
    def resolve(self, identity: BookIdentity, *, max_entities: int = 8) -> AliasResolution: ...
```

- [ ] **Step 1: Write fake-HTTP tests**

Test Chinese title → Japanese/English aliases, ISBN extraction, same-name film/game rejection, author mismatch downgrade, wrong-volume downgrade, and network failure becoming a warning instead of an overall exception.

- [ ] **Step 2: Run tests and confirm module absence**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q python-tests/cover/test_wikidata.py
```

- [ ] **Step 3: Implement two-stage entity lookup**

Use `wbsearchentities`, then `wbgetentities` for labels, aliases, descriptions, and claims. Parse title `P1476`, ISBN-13 `P212`, ISBN-10 `P957`, author `P50`, series `P179`, series ordinal `P1545`, and instance-of `P31`.

- [ ] **Step 4: Add confidence scoring and commit**

Only exact ISBN, or title/series/volume with compatible author, becomes high confidence. Medium results require confirmation; low results are discarded.

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/cover/test_wikidata.py python-tests/cover/test_query_plan.py

git add python/src/epub_a4_word/cover/search/wikidata.py \
  python/src/epub_a4_word/cover/search/__init__.py \
  python-tests/cover/test_wikidata.py
git commit -m "feat: resolve multilingual book aliases with wikidata"
```

---

### Task 9: Add the free Gutendex/Project Gutenberg provider

**Files:**
- Create: `python/src/epub_a4_word/cover/search/gutendex.py`
- Create: `python-tests/cover/test_gutendex.py`
- Modify: `python/src/epub_a4_word/cover/search/aggregate.py`
- Modify: `python/src/epub_a4_word/cover/search/__init__.py`

**Interfaces:**

```python
class GutendexProvider:
    name = "gutendex"
    def __init__(self, http: JsonHttpClient): ...
    def search(self, request: CoverSearchRequest) -> tuple[SearchCandidate, ...]: ...
```

- [ ] **Step 1: Write mapping tests**

Map `formats["image/jpeg"]` to an HTTPS front-cover candidate and source page `https://www.gutenberg.org/ebooks/<id>`. Ignore records without an image.

- [ ] **Step 2: Run tests and confirm module absence**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q python-tests/cover/test_gutendex.py
```

- [ ] **Step 3: Implement conservative querying**

Call `https://gutendex.com/books` with title/author search and optional language. Do not use Gutendex for back/spine/full-spread searches.

- [ ] **Step 4: Add provider order, test, and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/cover/test_gutendex.py python-tests/cover/test_round2_shared.py

git add python/src/epub_a4_word/cover/search/gutendex.py \
  python/src/epub_a4_word/cover/search/aggregate.py \
  python/src/epub_a4_word/cover/search/__init__.py \
  python-tests/cover/test_gutendex.py
git commit -m "feat: add free gutendex cover search"
```

---

### Task 10: Build the cross-language search pipeline and local alias cache

**Files:**
- Create: `python/src/epub_a4_word/cover/search/alias_cache.py`
- Create: `python/src/epub_a4_word/cover/search/pipeline.py`
- Create: `python-tests/cover/test_search_pipeline.py`
- Modify: `python/src/epub_a4_word/cover/search/google_books.py`
- Modify: `python/src/epub_a4_word/cover/search/open_library.py`
- Modify: `python/src/epub_a4_word/cover/search/aggregate.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ProviderSelection:
    google_books: bool = True
    open_library: bool = True
    gutendex: bool = True

class AliasCache:
    def load(self, identity: BookIdentity) -> tuple[ResolvedAlias, ...]: ...
    def remember(self, identity: BookIdentity, alias: ResolvedAlias,
                 isbn: str = "") -> None: ...
    def clear(self) -> None: ...

class BookCoverSearchPipeline:
    def search(self, metadata, *, selection: ProviderSelection,
               google_api_key: str = "", manual_alias: str = "") -> SearchResponse: ...
```

- [ ] **Step 1: Write orchestration tests**

Prove that missing API key skips only Google Books; Google Books titles/ISBNs and high-confidence Wikidata aliases create later Open Library queries; manual alias is highest title priority; duplicate normalized queries run once; one provider failure preserves other results; all-disabled is invalid; old-volume ISBN is never reused for a new volume; cache stores no EPUB/body data.

- [ ] **Step 2: Run tests and confirm pipeline absence**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q python-tests/cover/test_search_pipeline.py
```

- [ ] **Step 3: Extend Google Books as a bibliographic bridge**

Expose standardized title, authors, identifiers, language, and publisher for query expansion without overwriting EPUB metadata.

- [ ] **Step 4: Implement ordered query expansion**

Order: valid ISBN → manual alias → original title → normalized title → Google Books metadata → high-confidence Wikidata aliases. Open Library uses ISBN first, then manual/original-language/English/original EPUB names. Gutendex receives title queries only.

- [ ] **Step 5: Implement atomic local alias cache**

Use versioned JSON plus `os.replace`. Key by ISBN when valid, otherwise normalized title + author + volume. Series alias may cross volumes; ISBN may not.

- [ ] **Step 6: Run all search tests and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q \
  python-tests/cover/test_query_plan.py python-tests/cover/test_wikidata.py \
  python-tests/cover/test_gutendex.py python-tests/cover/test_search_pipeline.py \
  python-tests/cover/test_round2_shared.py

git add python/src/epub_a4_word/cover/search python-tests/cover
git commit -m "feat: add cross-language free cover search pipeline"
```

---

### Task 11: Replace the desktop search UI with free-source controls and alias visibility

**Files:**
- Modify: `python/src/epub_a4_word_desktop/cover/search_controller.py`
- Modify: `python/src/epub_a4_word_desktop/cover/search_panel.py`
- Modify: `python/src/epub_a4_word_desktop/settings/paths.py`
- Modify: `desktop/tests/test_cover_controller.py`
- Modify: `desktop/tests/test_cover_page.py`
- Modify: `desktop/tests/test_round2_desktop.py`

**Interfaces:**
- `SharedSearchFacade.search_public(metadata, credential, selection, manual_alias)` delegates to `BookCoverSearchPipeline`.
- UI exposes three provider checkboxes, one optional manual-alias field, and one search button.

- [ ] **Step 1: Write UI tests**

Assert all three providers are checked initially, manual alias placeholder is `原文書名／英文名／其他正式別名（選填）`, all-disabled state disables search, and missing Google key does not disable Open Library/Gutendex.

- [ ] **Step 2: Run tests and record old-control failures**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q \
  desktop/tests/test_cover_controller.py desktop/tests/test_cover_page.py \
  desktop/tests/test_round2_desktop.py
```

- [ ] **Step 3: Replace active Google Custom Search controls**

Add checkboxes for Google Books, Open Library, and Project Gutenberg; a manual alias line edit; one `搜尋封面` button; `Google Books API 設定`; and `清除別名快取`. Keep candidate cards and segmented/composite application.

- [ ] **Step 4: Show provider-specific status**

Keep successful cards when another provider warns. Display exact source labels such as `Google Books：未設定 API Key，已略過。`, `Open Library：暫時限流。`, and `Project Gutenberg：服務無法連線。`.

- [ ] **Step 5: Cache user-confirmed aliases**

After the user selects a matching candidate, remember manual or resolved aliases. Do not cache medium-confidence aliases merely because they were displayed.

- [ ] **Step 6: Run desktop tests and commit**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q \
  desktop/tests/test_cover_controller.py desktop/tests/test_cover_page.py \
  desktop/tests/test_round2_desktop.py desktop/tests/test_desktop_smoke.py

git add python/src/epub_a4_word_desktop/cover/search_controller.py \
  python/src/epub_a4_word_desktop/cover/search_panel.py \
  python/src/epub_a4_word_desktop/settings/paths.py desktop/tests
git commit -m "feat: add free-source and alias controls to cover search"
```

---

### Task 12: Complete compatibility, documentation, and cross-platform verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `BUILDING.md`
- Modify: `scripts/verify_project.py`
- Modify: `.github/workflows/desktop.yml`
- Modify: `.github/workflows/windows-portable.yml`
- Modify: relevant packaging/source-layout tests.

- [ ] **Step 1: Add source-layout and packaging assertions**

Require the new EPUB/search modules in source archives and Windows portable output. Confirm PyInstaller discovers them without hidden-import failures.

- [ ] **Step 2: Document final behavior**

Document API-key-only Google Books, no-key Open Library/Gutendex, Wikidata alias resolution, provider switches, manual original-title input, embedded front/back extraction, body-only default, A5 and 4×6 physical sizes, and that old DOCX/project files must be regenerated.

- [ ] **Step 3: Run complete shared tests**

```bash
PYTHONPATH=.:python/src:app/src/main/python pytest -q python-tests
```

- [ ] **Step 4: Run complete desktop and structural checks**

```bash
PYTHONPATH=.:python/src:app/src/main/python QT_QPA_PLATFORM=offscreen pytest -q desktop/tests
python -m compileall -q python/src app/src/main/python scripts
python scripts/verify_project.py
python scripts/desktop_smoke.py
```

- [ ] **Step 5: Verify fixtures manually**

Use: front-only EPUB; explicit front+back EPUB; normal final illustration; Chinese translated title resolving to Japanese original; same series with different volume; and three-page A5/4×6/B6 outputs. Inspect OOXML and rendered PDF page count/size. Record Microsoft Word real-device validation as pending until tested on the user’s Windows installation.

- [ ] **Step 6: Push and wait for CI**

Require desktop Windows/macOS/Ubuntu, Android/shared checks, and Windows portable build/EXE smoke. Do not merge pending or failed checks.

- [ ] **Step 7: Verify Windows portable artifact**

Require `EPUB2A4.exe` and `_internal/PySide6/plugins/platforms/qwindows.dll`; run `scripts/verify_windows_portable.py`, compute SHA-256, and preserve reports.

- [ ] **Step 8: Commit documentation and CI updates**

```bash
git add README.md CHANGELOG.md BUILDING.md scripts .github python-tests desktop/tests
git commit -m "docs: document free cover search and body-only conversion"
```

- [ ] **Step 9: Open the pull request**

Title: `feat: add free multilingual cover lookup and body-only conversion`.

The PR body must list the A5/4×6/B6 single-page OOXML fix, exact size checks, embedded front/back extraction, body-only default, free providers, credential migration, test totals, CI links, and the remaining Microsoft Word real-device caveat.

---

## Plan Self-Review

- **Spec coverage:** Free providers and switches are Tasks 7–11; multilingual names are Tasks 6, 8, and 10; embedded front/back extraction is Tasks 2 and 5; body-only default is Tasks 3 and 4; no automatic text/barcodes is Task 5; A5/4×6 size and blank-page regressions are Task 1; privacy, compatibility, packaging, and CI are Task 12.
- **Placeholder scan:** No TBD, TODO, `implement later`, or unspecified edge-handling step remains.
- **Type consistency:** `EpubStructure`, `BookIdentity`, `ResolvedAlias`, `QueryPlan`, `AliasResolution`, `ProviderSelection`, `AliasCache`, and `content_only` are defined before downstream use.
- **Scope:** Each task has a focused red-green-refactor cycle and an independently reviewable commit.