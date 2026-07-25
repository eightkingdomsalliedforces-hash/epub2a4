# Windows Cover Search and Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Windows cover workflow with automatic metadata-driven searches for existing front, back, spine, full-spread, and reference images, then let the user apply selected images through segmented editing or a composed full spread.

**Architecture:** Add provider-neutral search, classification, validated download, and composition units to the shared Python package. The PySide6 desktop layer owns background workers, credential persistence, candidate presentation, manual category correction, and undoable application to the existing cover project. Search never generates images and never applies a result without an explicit user action.

**Tech Stack:** Python 3.13, stdlib `urllib`, Pillow 11, PySide6 6.11, keyring 25.7, platformdirs 4.10, pytest/pytest-qt, PyInstaller 6.

## Global Constraints

- Search only existing images; do not call AI or any image-generation service.
- Public search sources are Google Books and Open Library.
- General image search uses Google Custom Search image mode with a user-supplied API Key and Search Engine ID.
- Do not scrape Google Images HTML pages.
- Automatic public search starts after a cover project is created from EPUB, DOCX, or PDF metadata.
- Stored Google credentials trigger automatic searches for front, back, spine, full spread, and reference photographs.
- Missing credentials must not open a blocking dialog; show `設定圖片搜尋` instead.
- Search results are never auto-applied and the first result is never silently selected.
- Candidate classification is heuristic and remains editable by the user.
- Selected downloads are HTTPS only, at most 50 MiB, and at most 20,000 × 20,000 decoded pixels.
- Search or network failure must not disable embedded-image or local-image workflows.
- Standard Windows mode uses the OS credential store when available.
- Portable mode defaults to session-only credentials; plaintext persistence requires a warning and a second confirmation.
- Development runs only focused tests for the changed unit, one desktop startup smoke check, and one final Windows portable build.

---

## File Structure

### Shared search package

- `python/src/epub_a4_word/cover/search/models.py`: immutable requests, credentials, candidates, classifications, and responses.
- `python/src/epub_a4_word/cover/search/errors.py`: stable search/download exceptions without credential leakage.
- `python/src/epub_a4_word/cover/search/http.py`: bounded HTTPS JSON requests and streaming downloads.
- `python/src/epub_a4_word/cover/search/google_books.py`: Google Books request and response normalization.
- `python/src/epub_a4_word/cover/search/open_library.py`: Open Library request and response normalization.
- `python/src/epub_a4_word/cover/search/google_custom.py`: explicit Google Custom Search image requests.
- `python/src/epub_a4_word/cover/search/aggregate.py`: merging, ranking, deduplication, and multi-kind general searches.
- `python/src/epub_a4_word/cover/search/classifier.py`: category proposal and confidence.
- `python/src/epub_a4_word/cover/search/download.py`: safe original-image download and validation.
- `python/src/epub_a4_word/cover/search/cache.py`: bounded URL-keyed image cache.
- `python/src/epub_a4_word/cover/composition.py`: front/back/spine to flat-spread raster composition.

### Windows desktop package

- `python/src/epub_a4_word_desktop/settings/paths.py`: standard and `portable.flag` runtime directories.
- `python/src/epub_a4_word_desktop/settings/credentials.py`: keyring, session, and confirmed portable stores.
- `python/src/epub_a4_word_desktop/cover/search_controller.py`: generation-safe search/download workers.
- `python/src/epub_a4_word_desktop/cover/search_panel.py`: metadata summary, search modes, result grid, and category editing.
- `python/src/epub_a4_word_desktop/cover/credential_dialog.py`: API credential entry and persistence choice.
- `python/src/epub_a4_word_desktop/cover/composition_dialog.py`: segmented/full-spread application choices and per-region fitting.

---

### Task 1: Provider Models, Errors, and Bounded HTTPS Transport

**Files:**
- Create: `python/src/epub_a4_word/cover/search/__init__.py`
- Create: `python/src/epub_a4_word/cover/search/models.py`
- Create: `python/src/epub_a4_word/cover/search/errors.py`
- Create: `python/src/epub_a4_word/cover/search/http.py`
- Create: `python-tests/cover/search/test_contracts.py`

**Interfaces:**
- Produces `SearchKind`, `CandidateCategory`, `CoverSearchRequest`, `ProviderCredential`, `SearchCandidate`, `CandidateClassification`, and `SearchResponse`.
- Produces `JsonHttpClient.get_json(url, params, headers=None) -> dict[str, object]`.
- Produces `JsonHttpClient.stream_download(url, destination, max_bytes) -> DownloadTransportResult`.

- [ ] **Step 1: Add the focused contract test**

```python
from pathlib import Path

import pytest

from epub_a4_word.cover.search.errors import SearchQuotaError, SearchTransportError
from epub_a4_word.cover.search.http import JsonHttpClient
from epub_a4_word.cover.search.models import (
    CandidateCategory,
    CoverSearchRequest,
    SearchCandidate,
    SearchKind,
)


def test_request_and_candidate_contracts_reject_unsafe_values(fake_opener):
    request = CoverSearchRequest(
        kind=SearchKind.FRONT,
        title="範例書",
        author="作者",
        locale="zh-TW",
        max_results=20,
    )
    candidate = SearchCandidate(
        provider="google_books",
        candidate_id="volume-1",
        query_kind=SearchKind.FRONT,
        proposed_category=CandidateCategory.FRONT,
        title="範例書",
        author="作者",
        isbn="9780000000001",
        preview_url="https://example.test/preview.jpg",
        image_url="https://example.test/original.jpg",
        source_page="https://example.test/book/1",
        width_px=1200,
        height_px=1800,
        media_type="image/jpeg",
        rights="",
    )
    assert request.max_results == 20
    assert candidate.rights_confirmed is False

    client = JsonHttpClient(opener=fake_opener)
    with pytest.raises(SearchTransportError, match="HTTPS"):
        client.get_json("http://example.test/data", {})
```

- [ ] **Step 2: Run the focused test and confirm the package is missing**

Run:

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_contracts.py -q
```

Expected: collection fails because `epub_a4_word.cover.search` does not exist.

- [ ] **Step 3: Implement immutable models and validation**

Use these public types:

```python
class SearchKind(StrEnum):
    FRONT = "front"
    BACK = "back"
    SPINE = "spine"
    FULL_SPREAD = "full_spread"
    REFERENCE_PHOTO = "reference_photo"


class CandidateCategory(StrEnum):
    FRONT = "front"
    BACK = "back"
    SPINE = "spine"
    FULL_SPREAD = "full_spread"
    REFERENCE_PHOTO = "reference_photo"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CoverSearchRequest:
    kind: SearchKind
    query: str = ""
    isbn: str = ""
    title: str = ""
    author: str = ""
    locale: str = "zh-TW"
    max_results: int = 20
    safe_search: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.max_results <= 40:
            raise ValueError("max_results 必須介於 1 與 40。")
        if not any(value.strip() for value in (self.query, self.isbn, self.title)):
            raise ValueError("搜尋至少需要關鍵字、ISBN 或書名。")


@dataclass(frozen=True)
class ProviderCredential:
    api_key: str
    search_engine_id: str


@dataclass(frozen=True)
class SearchCandidate:
    provider: str
    candidate_id: str
    query_kind: SearchKind
    proposed_category: CandidateCategory
    title: str
    author: str
    isbn: str
    preview_url: str
    image_url: str
    source_page: str
    width_px: int | None = None
    height_px: int | None = None
    media_type: str = ""
    rights: str = ""
    classification_confidence: float = 0.0

    @property
    def rights_confirmed(self) -> bool:
        return bool(self.rights.strip())
```

Require every non-empty candidate URL to use HTTPS. Do not place credentials in any model except `ProviderCredential`.

- [ ] **Step 4: Implement bounded and redacted transport**

Use:

```python
DEFAULT_TIMEOUT_SECONDS = 12
MAX_JSON_BYTES = 4 * 1024 * 1024
USER_AGENT = "EPUB2A4-CoverTool/0.6"
SENSITIVE_KEYS = {"key", "api_key", "cx", "search_engine_id"}
```

`get_json` must read at most `MAX_JSON_BYTES + 1`, map 401/403 to `SearchCredentialError`, 429 to `SearchQuotaError`, timeout to `SearchTimeoutError`, and all other failures to `SearchTransportError`. Error strings may contain the endpoint path and redacted parameter names but not parameter values for sensitive keys.

- [ ] **Step 5: Run the focused test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python/src/epub_a4_word/cover/search python-tests/cover/search/test_contracts.py
git commit -m "feat: add cover search contracts and transport"
```

---

### Task 2: Google Books, Open Library, Merge, and Ranking

**Files:**
- Create: `python/src/epub_a4_word/cover/search/google_books.py`
- Create: `python/src/epub_a4_word/cover/search/open_library.py`
- Create: `python/src/epub_a4_word/cover/search/aggregate.py`
- Create: `python-tests/cover/search/test_public_search.py`
- Create: `python-tests/fixtures/search/google-books-isbn.json`
- Create: `python-tests/fixtures/search/open-library-title.json`

**Interfaces:**
- Consumes Task 1 models and `JsonHttpClient`.
- Produces `GoogleBooksProvider.search(request) -> SearchResponse`.
- Produces `OpenLibraryProvider.search(request) -> SearchResponse`.
- Produces `PublicBookSearch.search(request) -> SearchResponse`.

- [ ] **Step 1: Add one fixture-based public-search test**

```python
def test_public_search_merges_deduplicates_and_ranks_exact_isbn(public_search):
    response = public_search.search(
        CoverSearchRequest(
            kind=SearchKind.FRONT,
            isbn="9780000000001",
            title="範例書",
            author="作者",
        )
    )
    assert response.candidates
    assert response.candidates[0].isbn == "9780000000001"
    assert len({candidate.normalized_identity for candidate in response.candidates}) == len(response.candidates)
    assert all(candidate.proposed_category is CandidateCategory.FRONT for candidate in response.candidates)
```

- [ ] **Step 2: Run and confirm provider modules are missing**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_public_search.py -q
```

Expected: collection error for missing provider modules.

- [ ] **Step 3: Implement Google Books normalization**

Request `https://www.googleapis.com/books/v1/volumes` with `isbn:<isbn>` when ISBN is available, otherwise `intitle:<title> inauthor:<author>`. Prefer `extraLarge`, `large`, `medium`, `small`, `thumbnail`, then `smallThumbnail`; normalize Google-hosted `http://` image links to HTTPS. Use `infoLink` or `canonicalVolumeLink` as the source page.

- [ ] **Step 4: Implement Open Library normalization**

Request `https://openlibrary.org/search.json` with ISBN or title/author and fields `key,title,author_name,isbn,cover_i,edition_key`. Build medium and large cover URLs from `cover_i`; skip records without a cover ID.

- [ ] **Step 5: Implement deterministic deduplication and ranking**

Rank in this order:

1. exact normalized ISBN;
2. exact normalized title and author;
3. exact title;
4. greater known pixel area;
5. provider order Google Books then Open Library;
6. candidate ID.

Use ISBN as the primary identity. Without ISBN, use normalized title, author, image host, and image path.

- [ ] **Step 6: Run the focused test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_public_search.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word/cover/search python-tests/cover/search/test_public_search.py python-tests/fixtures/search
git commit -m "feat: search public book cover databases"
```

---

### Task 3: General Image Queries and Editable Candidate Classification

**Files:**
- Create: `python/src/epub_a4_word/cover/search/google_custom.py`
- Create: `python/src/epub_a4_word/cover/search/classifier.py`
- Modify: `python/src/epub_a4_word/cover/search/aggregate.py`
- Create: `python-tests/cover/search/test_general_classification.py`
- Create: `python-tests/fixtures/search/google-custom-cover-parts.json`

**Interfaces:**
- Produces `GoogleCustomSearchProvider.search(request, credential) -> SearchResponse`.
- Produces `build_general_requests(metadata) -> tuple[CoverSearchRequest, ...]`.
- Produces `classify_candidate(candidate, requested_kind) -> CandidateClassification`.
- Produces `GeneralCoverSearch.search_all(metadata, credential) -> SearchResponse`.

- [ ] **Step 1: Add one multi-kind classification test**

```python
def test_general_search_keeps_query_kind_and_proposes_editable_categories(general_search):
    response = general_search.search_all(
        title="範例書",
        author="作者",
        isbn="9780000000001",
        locale="zh-TW",
        credential=ProviderCredential("secret-key", "engine-id"),
    )
    categories = {candidate.proposed_category for candidate in response.candidates}
    assert CandidateCategory.BACK in categories
    assert CandidateCategory.SPINE in categories
    assert CandidateCategory.FULL_SPREAD in categories
    serialized = response.to_dict()
    assert "secret-key" not in repr(serialized)
    assert "engine-id" not in repr(serialized)
```

- [ ] **Step 2: Run and confirm the provider/classifier is absent**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_general_classification.py -q
```

Expected: collection error.

- [ ] **Step 3: Implement explicit Google Custom Search image requests**

Use endpoint `https://customsearch.googleapis.com/customsearch/v1` and parameters:

```python
{
    "key": credential.api_key,
    "cx": credential.search_engine_id,
    "q": request.query,
    "searchType": "image",
    "num": min(request.max_results, 10),
    "safe": "active" if request.safe_search else "off",
    "hl": request.locale,
}
```

Require both credential fields. Parse `items[].link`, `items[].image.thumbnailLink`, `items[].image.contextLink`, width, height, MIME, and title. Reject non-HTTPS image or context links.

- [ ] **Step 4: Build five distinct localized queries**

For each metadata set, create requests for:

```python
QUERY_TERMS = {
    SearchKind.FRONT: ("封面", "front cover"),
    SearchKind.BACK: ("背面", "back cover"),
    SearchKind.SPINE: ("書脊", "book spine"),
    SearchKind.FULL_SPREAD: ("完整書衣 展開圖", "full dust jacket wraparound cover"),
    SearchKind.REFERENCE_PHOTO: ("實拍 多角度", "book photos alternate angles"),
}
```

Combine quoted title, author, ISBN, and the kind terms. Run sequentially in the shared unit so API usage is explicit and warning aggregation is deterministic.

- [ ] **Step 5: Implement heuristic classification**

Return `CandidateClassification(category, confidence, reasons)`. Start from the request kind, then adjust with filename/title/source keywords and aspect ratio. Use these rules:

- `spine`: width/height ≤ 0.28 or spine keywords;
- `full_spread`: width/height ≥ 1.35 or spread/wraparound keywords;
- `back`: back/rear/背面 keywords;
- `front`: front/cover/封面 keywords when no stronger rule applies;
- `reference_photo`: photo, angle, side view, 實拍, 多角度 keywords;
- confidence below 0.55 displays as `unknown` while retaining reasons.

Classification only proposes a category; the desktop UI stores user corrections separately.

- [ ] **Step 6: Run the focused test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_general_classification.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word/cover/search python-tests/cover/search/test_general_classification.py python-tests/fixtures/search
git commit -m "feat: search and classify complete cover imagery"
```

---

### Task 4: Validated Download, Cache, and Shared Service Boundary

**Files:**
- Create: `python/src/epub_a4_word/cover/search/download.py`
- Create: `python/src/epub_a4_word/cover/search/cache.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Create: `python-tests/cover/search/test_download_service.py`

**Interfaces:**
- Produces `download_candidate(candidate, destination, http_client) -> DownloadedImage`.
- Produces `ImageCache(root, max_bytes=209715200)`.
- Adds `service.search_covers(request_json: str) -> str`.
- Adds `service.download_search_candidate(candidate_json: str, destination_path: str) -> dict[str, object]`.

- [ ] **Step 1: Add one safety/service test**

```python
def test_download_service_rejects_html_and_never_leaves_partial_file(tmp_path, fake_http):
    destination = tmp_path / "selected.jpg"
    fake_http.respond(content_type="text/html", body=b"<html></html>")
    with pytest.raises(ImageDownloadError, match="圖片"):
        download_candidate(candidate(), destination, fake_http)
    assert not destination.exists()
    assert not destination.with_suffix(".jpg.part").exists()
```

- [ ] **Step 2: Run and confirm download module is absent**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_download_service.py -q
```

Expected: collection error.

- [ ] **Step 3: Implement streaming validation**

Use:

```python
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/tiff", "image/bmp"
}
```

Write to `<destination>.part`, stop before reading beyond the byte limit, verify the MIME, run Pillow `verify()`, reopen, load dimensions, reject either dimension above 20,000, then atomically replace the destination. Return content type, byte count, width, height, and SHA-256.

- [ ] **Step 4: Implement a bounded cache**

Key files by SHA-256 of a normalized image URL. Store an atomic `index.json` containing only cache key, size, access time, content type, width, and height. Do not store API request URLs or credentials. Evict least-recently-used entries until the total is at most 200 MiB.

- [ ] **Step 5: Add JSON service methods**

`search_covers` accepts:

```json
{
  "mode": "public_books|general_images",
  "kind": "front|back|spine|full_spread|reference_photo",
  "query": "",
  "isbn": "",
  "title": "",
  "author": "",
  "locale": "zh-TW",
  "max_results": 20,
  "safe_search": true,
  "credential": {"api_key": "", "search_engine_id": ""}
}
```

Public mode ignores credentials. General mode passes credentials for that call only and never serializes them into the response.

- [ ] **Step 6: Run the focused test**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_download_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word/cover/search python/src/epub_a4_word/cover/service.py python-tests/cover/search/test_download_service.py
git commit -m "feat: validate and cache selected cover images"
```

---

### Task 5: Windows Runtime Paths and Credential Stores

**Files:**
- Create: `python/src/epub_a4_word_desktop/settings/__init__.py`
- Create: `python/src/epub_a4_word_desktop/settings/paths.py`
- Create: `python/src/epub_a4_word_desktop/settings/credentials.py`
- Modify: `python/src/epub_a4_word_desktop/app.py`
- Modify: `python/src/epub_a4_word_desktop/main_window.py`
- Modify: `packaging/windows/EPUB2A4.spec`
- Create: `desktop/tests/test_search_settings.py`

**Interfaces:**
- Produces `RuntimePaths(mode, config_dir, cache_dir, data_dir)`.
- Produces `resolve_runtime_paths(executable_dir) -> RuntimePaths`.
- Produces `CredentialStore.load/save/clear` implementations for keyring, session, and confirmed portable JSON.
- `MainWindow(runtime_paths: RuntimePaths | None = None)` passes paths into `CoverPage`.

- [ ] **Step 1: Add one paths/credential test**

```python
def test_portable_mode_uses_session_credentials_until_plaintext_is_confirmed(tmp_path):
    (tmp_path / "portable.flag").write_text("1", encoding="ascii")
    paths = resolve_runtime_paths(tmp_path)
    assert paths.mode == "portable"
    session = SessionCredentialStore()
    session.save(ProviderCredential("key", "cx"))
    assert session.load() == ProviderCredential("key", "cx")
    with pytest.raises(CredentialPersistenceWarning):
        PortableCredentialStore(paths.config_dir / "credentials.json").save(
            ProviderCredential("key", "cx"), confirmed_plaintext=False
        )
```

- [ ] **Step 2: Run and confirm settings package is absent**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_search_settings.py -q
```

Expected: collection error.

- [ ] **Step 3: Implement runtime path resolution**

`portable.flag` beside the executable selects `data/config`, `data/cache`, and `data/projects`. Verify `data/` is writable with a create/delete probe. Standard mode uses `platformdirs.user_config_path`, `user_cache_path`, and `user_data_path` for app name `EPUB2A4`.

- [ ] **Step 4: Implement credential stores**

- `KeyringCredentialStore`: service `EPUB2A4 Google Image Search`, usernames `api-key` and `search-engine-id`.
- `SessionCredentialStore`: memory only.
- `PortableCredentialStore`: writes JSON only when `confirmed_plaintext=True`; use mode `0600` where supported.
- A keyring failure returns a session store and a user-visible warning; it never silently falls back to plaintext.

- [ ] **Step 5: Wire paths into desktop startup and packaging**

Resolve paths once in `app.py`, pass them to `MainWindow`, then `CoverPage`. Add an empty `portable.flag` to the PyInstaller `COLLECT` output so the Windows portable ZIP uses portable paths by default.

- [ ] **Step 6: Run the focused test**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_search_settings.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word_desktop/settings python/src/epub_a4_word_desktop/app.py python/src/epub_a4_word_desktop/main_window.py packaging/windows/EPUB2A4.spec desktop/tests/test_search_settings.py
git commit -m "feat: add Windows cover-search settings storage"
```

---

### Task 6: Asynchronous Windows Search Workspace

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/search_controller.py`
- Create: `python/src/epub_a4_word_desktop/cover/search_panel.py`
- Create: `python/src/epub_a4_word_desktop/cover/credential_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Create: `desktop/tests/test_cover_search_workspace.py`

**Interfaces:**
- Produces `SearchController.search_public(metadata)` and `search_general(metadata, credential=None)`.
- Produces generation-tagged `results_ready`, `search_failed`, `credential_required`, and `download_ready` signals.
- Produces `CoverSearchPanel.bind_project(project_json)` and `candidate_selected(candidate, category)`.

- [ ] **Step 1: Add one focused workspace test**

```python
def test_binding_project_starts_public_search_without_modal_credentials(qtbot, fake_search_service):
    controller = SearchController(fake_search_service, credential_store=EmptyCredentialStore())
    panel = CoverSearchPanel(controller)
    qtbot.addWidget(panel)
    panel.bind_project(project_json_with_metadata(title="範例書", author="作者"))
    assert fake_search_service.public_calls == 1
    assert fake_search_service.general_calls == 0
    assert panel.configure_credentials_button.isVisible()
```

- [ ] **Step 2: Run and confirm UI modules are absent**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_search_workspace.py -q
```

Expected: collection error.

- [ ] **Step 3: Implement generation-safe workers**

Every search gets an increasing generation integer. Ignore completed signals whose generation is not current or whose panel is inactive. Public and general failures emit separate warnings so partial public results remain visible when general search fails.

Map failures to Traditional Chinese:

```python
ERROR_MESSAGES = {
    SearchCredentialError: "Google 圖片搜尋憑證無效，請重新設定。",
    SearchQuotaError: "搜尋配額已用完，請稍後重試或更換 API Key。",
    SearchTimeoutError: "搜尋逾時，請檢查網路後重試。",
    ImageDownloadError: "選取的圖片無法下載或格式不受支援。",
}
```

- [ ] **Step 4: Build the full-width search workspace**

In `CoverPage`, replace the center widget with a `QTabWidget` containing:

- `封面編輯`: existing canvas and zoom controls;
- `搜尋封面`: `CoverSearchPanel`.

Do not automatically switch tabs when background search starts. Candidate cards show preview, proposed category combo, title/source host, provider, resolution, source action, rights warning, and `選擇`.

- [ ] **Step 5: Implement automatic search timing**

After `_create_project` completes, call `search_panel.bind_project(self.controller.project_json)`. The panel tracks the source path plus metadata fingerprint so repeated preview/project mutations do not restart network searches. Binding starts public search immediately. It starts general multi-kind search only when the credential store already contains both values.

- [ ] **Step 6: Implement credential dialog behavior**

Buttons:

- `儲存到 Windows` for keyring;
- `僅本次使用`;
- in portable mode, `儲存到可攜資料夾`, followed by a second plaintext-risk confirmation;
- `清除已儲存`.

API Key is masked with a reveal toggle; Search Engine ID remains visible.

- [ ] **Step 7: Run the focused test**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_cover_search_workspace.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add python/src/epub_a4_word_desktop/cover python/src/epub_a4_word_desktop/pages/cover_page.py desktop/tests/test_cover_search_workspace.py
git commit -m "feat: add Windows automatic cover search workspace"
```

---

### Task 7: Segmented Editing and Composite Full-Spread Application

**Files:**
- Create: `python/src/epub_a4_word/cover/composition.py`
- Create: `python/src/epub_a4_word_desktop/cover/composition_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Create: `python-tests/cover/test_composition.py`
- Create: `desktop/tests/test_cover_candidate_application.py`

**Interfaces:**
- Produces `CompositionSelection(path, category, crop_left, crop_top, crop_right, crop_bottom, scale, offset_x, offset_y)`.
- Produces `compose_full_spread(project, selections, output_path, dpi) -> Path`.
- Adds `CoverController.add_downloaded_image(path, region, label)`.
- Adds `CoverController.add_composed_spread(path)`.

- [ ] **Step 1: Add one core composition geometry test**

```python
def test_composition_places_back_spine_front_in_print_order(tmp_path, project, solid_images):
    output = tmp_path / "spread.png"
    compose_full_spread(
        project,
        {
            CandidateCategory.BACK: selection(solid_images["red"]),
            CandidateCategory.SPINE: selection(solid_images["green"]),
            CandidateCategory.FRONT: selection(solid_images["blue"]),
        },
        output,
        dpi=100,
    )
    image = Image.open(output).convert("RGB")
    assert sample_region(image, "back") == (255, 0, 0)
    assert sample_region(image, "spine") == (0, 255, 0)
    assert sample_region(image, "front") == (0, 0, 255)
```

- [ ] **Step 2: Run and confirm composition is missing**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/test_composition.py -q
```

Expected: collection error.

- [ ] **Step 3: Implement shared composition**

Use `calculate_layout(project)` to obtain back, spine, front, and bleed rectangles. Convert millimetres to pixels at the requested DPI. Render a transparent RGBA canvas for the bleed rectangle. For each supplied selection, crop using normalized crop values, apply scale and offset, and paste into its target region with clipping. Missing regions remain transparent. Save PNG atomically.

- [ ] **Step 4: Implement the application dialog**

When a candidate is selected, the dialog provides:

- editable category;
- `分區編輯`;
- `合成完整書衣`;
- crop/scale/offset controls for the chosen region;
- a list of currently selected front/back/spine candidates;
- direct-use mode when the candidate is already `full_spread`.

`分區編輯` downloads and adds each chosen image to `Region.FRONT`, `Region.BACK`, or `Region.SPINE`. `合成完整書衣` writes one PNG and adds it to `Region.SPREAD`.

- [ ] **Step 5: Make mutations undoable**

Use the existing `ReplaceProjectCommand`. A segmented multi-image application is one undo step: construct the complete candidate project JSON first, then push one replacement command. A composed spread is also one replacement command.

- [ ] **Step 6: Run the two focused tests**

```bash
PYTHONPATH=python/src QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  python-tests/cover/test_composition.py \
  desktop/tests/test_cover_candidate_application.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/src/epub_a4_word/cover/composition.py python/src/epub_a4_word_desktop/cover python/src/epub_a4_word_desktop/pages/cover_page.py python-tests/cover/test_composition.py desktop/tests/test_cover_candidate_application.py
git commit -m "feat: apply searched cover parts as segments or spread"
```

---

### Task 8: Focused Integration Check and Final Windows Portable Build

**Files:**
- Modify: `packaging/windows/EPUB2A4.spec`
- Modify: `.github/workflows/windows-portable.yml`
- Modify: `README.md`
- Modify: `BUILD_STATUS.md`

**Interfaces:**
- Ensures PyInstaller includes `keyring`, platformdirs, search package modules, and `portable.flag`.
- Produces the final portable ZIP for manual user testing.

- [ ] **Step 1: Update PyInstaller collection**

Collect keyring backends and the new shared/desktop search modules. Keep `console=False`. Ensure `portable.flag` is beside `EPUB2A4.exe`, not under `_internal`.

- [ ] **Step 2: Add one non-network packaged smoke action**

The packaged smoke flag starts the window offscreen, opens the cover page, constructs the search panel without issuing a real request, then closes. Do not add live API calls to CI.

- [ ] **Step 3: Run only the desktop startup smoke check locally or in Actions**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=python/src python3.13 -m epub_a4_word_desktop --portable-smoke-test
```

Expected: exit code 0.

- [ ] **Step 4: Build the Windows portable package once**

Run the existing `Windows Portable` workflow. Required successful stages are installation, focused tests already named in this plan, source smoke, PyInstaller, packaged EXE smoke, ZIP creation, and artifact upload.

- [ ] **Step 5: Update documentation without claiming live-search success**

Document credential setup, automatic-search timing, category correction, segmented/full-spread application, and the fact that results are existing web images. Mark real Google Books/Open Library/Google Custom results as requiring user validation on Windows.

- [ ] **Step 6: Commit**

```bash
git add packaging/windows/EPUB2A4.spec .github/workflows/windows-portable.yml README.md BUILD_STATUS.md
git commit -m "build: package Windows cover search workflow"
```

- [ ] **Step 7: Deliver for manual validation**

Provide the portable ZIP and ask the user to test:

1. embedded cover appears immediately;
2. public search starts from detected metadata;
3. stored credentials trigger all five general searches;
4. category can be corrected;
5. segmented application is editable and undoable;
6. composite spread order is back–spine–front;
7. no image is generated or auto-applied.
