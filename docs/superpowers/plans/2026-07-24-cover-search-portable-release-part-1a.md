# Cover Search, Credentials, and Portable Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in cover search with multiple candidates, secure local credential handling, validated image download/cache, and portable Windows/macOS/Linux release artifacts while preserving independent Android packaging.

**Architecture:** Implement provider request/response normalization in the shared Python package so Android and desktop interpret Google Books, Open Library, and Google Custom Search identically. Platform layers own credentials and user interaction, pass credentials only for one request, display source/use-right warnings, and copy a selected image into the current cover project before editing.

**Tech Stack:** Python 3.13 stdlib HTTPS/JSON, Pillow, pytest; Google Books API, Open Library APIs, Google Custom Search JSON API; Android Keystore AES-GCM, Compose, Coil 3.5.0; desktop keyring 25.7.0, platformdirs 4.10.1; PyInstaller, AppImage tooling, GitHub Actions.

## Global Constraints

- This plan starts after the shared core, desktop editor, and Android editor plans pass.
- Search order: ISBN in public book databases, title+author in public book databases, then optional general image search.
- Public providers: Google Books and Open Library.
- General image provider in the first release: Google Custom Search image mode.
- General search requires a user-supplied API Key and Search Engine ID; no shared credential may appear in source, APK, desktop package, CI logs, fixtures, or crash output.
- Search shows multiple candidates and never auto-selects the first result.
- General image search occurs only after the user explicitly switches to it and presses Search.
- All requests use HTTPS and bounded timeouts.
- Source EPUB/DOCX/PDF files are never uploaded; requests contain only ISBN, title, author, locale, or user-entered keywords.
- Search failure never disables local/embedded cover creation.
- Selected image downloads are limited to 50 MiB and 20,000 × 20,000 decoded pixels.
- UI displays source page and `授權狀態未確認；使用者需自行確認使用權` unless a provider supplies an explicit rights value.
- Android network permission is added only in this plan.
- Desktop packages are portable and perform no version check or automatic update.
- Standard desktop mode stores settings in platform user-data directories; portable mode activates with `portable.flag` and writes beneath `data/`.

---

## Subpart A: Tasks 1–2

### Task 1: Define provider models, transport, errors, and response fixtures

**Files:**
- Create: `python/src/epub_a4_word/cover/search/__init__.py`
- Create: `python/src/epub_a4_word/cover/search/models.py`
- Create: `python/src/epub_a4_word/cover/search/http.py`
- Create: `python/src/epub_a4_word/cover/search/errors.py`
- Create: `python-tests/cover/search/test_http.py`
- Create: `python-tests/fixtures/search/`

**Interfaces:**
- Produces `CoverSearchRequest`, `SearchCandidate`, `SearchResponse`, `ProviderCredential`.
- Produces protocol `CoverSearchProvider.search(request, credential=None) -> SearchResponse`.
- Produces `JsonHttpClient.get_json(url, params, headers=None) -> dict` and `JsonHttpClient.stream_download`.

- [ ] **Step 1: Write failing model and transport tests**

```python
def test_candidate_serializes_required_source_fields():
    candidate = SearchCandidate(
        provider="google_books",
        candidate_id="volume-1",
        title="範例書",
        author="作者",
        preview_url="https://example.test/preview.jpg",
        image_url="https://example.test/full.jpg",
        source_page="https://example.test/book/1",
        width_px=1200,
        height_px=1800,
        rights="",
    )
    raw = candidate.to_dict()
    assert raw["provider"] == "google_books"
    assert raw["source_page"].startswith("https://")
    assert raw["rights_confirmed"] is False


def test_http_rejects_non_https():
    client = JsonHttpClient(opener=FakeOpener())
    with pytest.raises(SearchTransportError, match="HTTPS"):
        client.get_json("http://example.test/data", {})


def test_http_maps_429_to_quota_error():
    client = JsonHttpClient(opener=FakeOpener(status=429, body=b"{}"))
    with pytest.raises(SearchQuotaError):
        client.get_json("https://example.test/data", {})
```

- [ ] **Step 2: Run tests and verify missing modules fail**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_http.py -q
```

Expected: collection ERROR because the search package does not exist.

- [ ] **Step 3: Implement immutable request/candidate models**

```python
@dataclass(frozen=True)
class CoverSearchRequest:
    query: str = ""
    isbn: str = ""
    title: str = ""
    author: str = ""
    locale: str = "zh-TW"
    max_results: int = 20
    safe_search: bool = True


@dataclass(frozen=True)
class ProviderCredential:
    api_key: str
    search_engine_id: str = ""


@dataclass(frozen=True)
class SearchCandidate:
    provider: str
    candidate_id: str
    title: str
    author: str
    preview_url: str
    image_url: str
    source_page: str
    width_px: int | None = None
    height_px: int | None = None
    media_type: str = ""
    rights: str = ""

    @property
    def rights_confirmed(self) -> bool:
        return bool(self.rights.strip())
```

Validate `max_results` in `1..40`, require at least one of query/isbn/title, and require HTTPS for every non-empty URL.

- [ ] **Step 4: Implement bounded JSON transport**

`JsonHttpClient` uses `urllib.request` with:

```python
DEFAULT_TIMEOUT_SECONDS = 12
MAX_JSON_BYTES = 4 * 1024 * 1024
USER_AGENT = "EPUB2A4-CoverTool/0.6"
```

Read at most `MAX_JSON_BYTES + 1`; reject oversized responses; decode UTF-8; map 401/403 to `SearchCredentialError`, 429 to `SearchQuotaError`, other HTTP errors to `SearchTransportError`; never include query credential values in exception text.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_http.py -q
git add python/src/epub_a4_word/cover/search python-tests/cover/search python-tests/fixtures/search
git commit -m "feat: add cover search provider contracts"
```

Expected: PASS.

---

### Task 2: Implement Google Books and Open Library providers

**Files:**
- Create: `python/src/epub_a4_word/cover/search/google_books.py`
- Create: `python/src/epub_a4_word/cover/search/open_library.py`
- Create: `python/src/epub_a4_word/cover/search/aggregate.py`
- Create: `python-tests/cover/search/test_google_books.py`
- Create: `python-tests/cover/search/test_open_library.py`
- Create: `python-tests/cover/search/test_aggregate.py`
- Add fixtures: `python-tests/fixtures/search/google-books-*.json`
- Add fixtures: `python-tests/fixtures/search/open-library-*.json`

**Interfaces:**
- `GoogleBooksProvider.search(request) -> SearchResponse`.
- `OpenLibraryProvider.search(request) -> SearchResponse`.
- `PublicBookSearch.search(request) -> SearchResponse` queries both, merges, deduplicates, and ranks candidates.

- [ ] **Step 1: Add failing fixture-parsing tests**

```python
def test_google_books_uses_largest_https_cover(fixture_http):
    provider = GoogleBooksProvider(fixture_http("google-books-isbn.json"))
    result = provider.search(CoverSearchRequest(isbn="9780000000001"))
    candidate = result.candidates[0]
    assert candidate.provider == "google_books"
    assert candidate.image_url.startswith("https://")
    assert candidate.source_page.startswith("https://")


def test_open_library_uses_cover_id_large_url(fixture_http):
    provider = OpenLibraryProvider(fixture_http("open-library-title.json"))
    result = provider.search(CoverSearchRequest(title="範例書", author="作者"))
    assert result.candidates[0].image_url.endswith("-L.jpg")


def test_aggregate_deduplicates_isbn_and_near_identical_urls(public_search):
    result = public_search.search(CoverSearchRequest(isbn="9780000000001"))
    assert len({c.normalized_identity for c in result.candidates}) == len(result.candidates)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest \
  python-tests/cover/search/test_google_books.py \
  python-tests/cover/search/test_open_library.py \
  python-tests/cover/search/test_aggregate.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement Google Books query and parsing**

Endpoint and parameters:

```python
BASE_URL = "https://www.googleapis.com/books/v1/volumes"
query = f"isbn:{request.isbn}" if request.isbn else " ".join(
    part for part in (f'intitle:{request.title}' if request.title else "", f'inauthor:{request.author}' if request.author else "") if part
)
params = {"q": query, "maxResults": min(request.max_results, 40), "langRestrict": request.locale.split("-")[0]}
```

Parse `volumeInfo.imageLinks` in priority order `extraLarge`, `large`, `medium`, `small`, `thumbnail`, `smallThumbnail`; normalize `http://` Google image links to `https://`; candidate ID is volume `id`; source page is `infoLink` or `canonicalVolumeLink`.

- [ ] **Step 4: Implement Open Library query and parsing**

Use `https://openlibrary.org/search.json` with `isbn` or `title`/`author`, fields `key,title,author_name,isbn,cover_i,edition_key`, and `limit`. Build cover URLs as:

```python
preview = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
image = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
source = f"https://openlibrary.org{work_key}"
```

Skip entries without `cover_i`.

- [ ] **Step 5: Implement deterministic merge/ranking**

Ranking:

1. exact normalized ISBN match;
2. exact normalized title+author match;
3. exact title;
4. higher known pixel area;
5. provider order Google Books then Open Library;
6. candidate ID.

Deduplicate by normalized ISBN where present, otherwise normalized title/author plus image host/path.

```python
PROVIDER_ORDER = {"google_books": 0, "open_library": 1, "google_custom": 2}


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _candidate_key(candidate: SearchCandidate) -> tuple[str, ...]:
    if candidate.isbn:
        return ("isbn", re.sub(r"[^0-9Xx]", "", candidate.isbn))
    parsed = urllib.parse.urlsplit(candidate.image_url)
    return (
        "metadata-url",
        _normalize(candidate.title),
        _normalize(candidate.author),
        parsed.netloc.casefold(),
        parsed.path,
    )


def _rank(candidate: SearchCandidate, request: CoverSearchRequest) -> tuple[object, ...]:
    request_isbn = re.sub(r"[^0-9Xx]", "", request.isbn or "")
    candidate_isbn = re.sub(r"[^0-9Xx]", "", candidate.isbn or "")
    exact_isbn = bool(request_isbn and candidate_isbn == request_isbn)
    exact_title = _normalize(candidate.title) == _normalize(request.title)
    exact_author = _normalize(candidate.author) == _normalize(request.author)
    pixel_area = (candidate.width or 0) * (candidate.height or 0)
    return (
        0 if exact_isbn else 1,
        0 if exact_title and exact_author else 1,
        0 if exact_title else 1,
        -pixel_area,
        PROVIDER_ORDER[candidate.provider],
        candidate.id,
    )


def merge_candidates(
    candidates: Iterable[SearchCandidate],
    request: CoverSearchRequest,
) -> list[SearchCandidate]:
    unique: dict[tuple[str, ...], SearchCandidate] = {}
    for candidate in candidates:
        key = _candidate_key(candidate)
        current = unique.get(key)
        if current is None or _rank(candidate, request) < _rank(current, request):
            unique[key] = candidate
    return sorted(unique.values(), key=lambda item: _rank(item, request))
```

- [ ] **Step 6: Run tests and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search -q
git add python/src/epub_a4_word/cover/search python-tests/cover/search python-tests/fixtures/search
git commit -m "feat: search public book cover databases"
```

Expected: PASS.

---
