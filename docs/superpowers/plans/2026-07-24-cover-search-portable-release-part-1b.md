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

## Subpart B: Tasks 3–4

### Task 3: Implement extensible Google Custom Search image provider

**Files:**
- Create: `python/src/epub_a4_word/cover/search/google_custom.py`
- Modify: `python/src/epub_a4_word/cover/search/aggregate.py`
- Create: `python-tests/cover/search/test_google_custom.py`
- Add fixtures: `python-tests/fixtures/search/google-custom-*.json`

**Interfaces:**
- `GoogleCustomSearchProvider.search(request, credential) -> SearchResponse`.
- General provider registry maps provider ID to factory; first release registers only `google_custom`.
- Credentials are function arguments only and are never retained by provider instances or response objects.

- [ ] **Step 1: Write failing request and parsing tests**

```python
def test_custom_search_requires_both_credential_fields():
    provider = GoogleCustomSearchProvider(FakeHttp())
    with pytest.raises(SearchCredentialError, match="API Key"):
        provider.search(CoverSearchRequest(query="範例書 封面"), ProviderCredential("", ""))


def test_custom_search_uses_image_mode_and_safe_search(recording_http):
    provider = GoogleCustomSearchProvider(recording_http)
    provider.search(
        CoverSearchRequest(query="範例書 封面", safe_search=True),
        ProviderCredential("secret-key", "engine-id"),
    )
    params = recording_http.last_params_without_secrets
    assert params["searchType"] == "image"
    assert params["safe"] == "active"
    assert params["num"] == 10


def test_custom_candidate_contains_context_source(fixture_http):
    result = GoogleCustomSearchProvider(fixture_http("google-custom-success.json")).search(
        CoverSearchRequest(query="範例書"), ProviderCredential("key", "cx")
    )
    candidate = result.candidates[0]
    assert candidate.source_page == "https://publisher.example/book"
    assert candidate.width_px == 1200
    assert candidate.height_px == 1800
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search/test_google_custom.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement the provider request**

Use:

```python
BASE_URL = "https://customsearch.googleapis.com/customsearch/v1"
params = {
    "key": credential.api_key,
    "cx": credential.search_engine_id,
    "q": request.query or " ".join(filter(None, (request.title, request.author, "book cover"))),
    "searchType": "image",
    "num": min(request.max_results, 10),
    "safe": "active" if request.safe_search else "off",
    "hl": request.locale,
}
```

Parse `items[].link` as full image, `items[].image.thumbnailLink` as preview, `items[].image.contextLink` as source page, image width/height, MIME, title, and display link. Reject non-HTTPS image/context URLs.

- [ ] **Step 4: Make logs and errors credential-safe**

Before recording request diagnostics, redact keys `key`, `api_key`, `cx`, `search_engine_id`; fixture recorders assert secrets do not appear in `repr(error)`, warning lists, or response serialization.

```python
SENSITIVE_KEYS = {"key", "api_key", "cx", "search_engine_id"}


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    return {
        key: "<redacted>" if key.casefold() in SENSITIVE_KEYS else value
        for key, value in values.items()
    }


def safe_request_description(url: str, params: Mapping[str, object]) -> str:
    parsed = urllib.parse.urlsplit(url)
    clean_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return f"GET {clean_url} params={redact_mapping(params)!r}"


class SearchTransportError(CoverSearchError):
    def __init__(self, message: str, *, url: str, params: Mapping[str, object]) -> None:
        super().__init__(f"{message}; {safe_request_description(url, params)}")
```

```python
def test_error_repr_redacts_credentials():
    error = SearchTransportError(
        "request failed",
        url="https://example.test/search?key=SECRET",
        params={"key": "SECRET", "cx": "ENGINE", "q": "book"},
    )
    assert "SECRET" not in repr(error)
    assert "ENGINE" not in repr(error)
```

- [ ] **Step 5: Register the provider and commit**

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests/cover/search -q
git add python/src/epub_a4_word/cover/search python-tests/cover/search python-tests/fixtures/search
git commit -m "feat: add Google image search provider"
```

Expected: PASS.

---

### Task 4: Validate, download, and cache selected images

**Files:**
- Create: `python/src/epub_a4_word/cover/search/download.py`
- Create: `python/src/epub_a4_word/cover/search/cache.py`
- Create: `python-tests/cover/search/test_download.py`
- Create: `python-tests/cover/search/test_cache.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Modify: `app/src/main/python/android_bridge.py`

**Interfaces:**
- Produces `download_candidate(candidate, destination_path) -> DownloadedImage`.
- Produces `SearchCache(cache_dir, max_bytes=200 MiB)` for thumbnails and selected originals.
- Service `search_covers(request_json) -> str` and `download_candidate(candidate_json, destination_path) -> dict` become active.

- [ ] **Step 1: Write failing security and cache tests**

```python
def test_rejects_non_image_content(fake_download):
    fake_download.respond(content_type="text/html", body=b"<html></html>")
    with pytest.raises(ImageDownloadError, match="圖片"):
        download_candidate(candidate(), fake_download.destination)


def test_rejects_oversized_stream_before_full_download(fake_download):
    fake_download.respond(content_type="image/jpeg", content_length=50 * 1024 * 1024 + 1)
    with pytest.raises(ImageDownloadError, match="50 MiB"):
        download_candidate(candidate(), fake_download.destination)


def test_cache_evicts_oldest_entries(tmp_path):
    cache = SearchCache(tmp_path, max_bytes=100)
    cache.put("a", b"a" * 60)
    cache.put("b", b"b" * 60)
    assert cache.get("a") is None
    assert cache.get("b") == b"b" * 60
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONPATH=python/src python3.13 -m pytest \
  python-tests/cover/search/test_download.py python-tests/cover/search/test_cache.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement streaming validation**

Rules:

```python
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"
}
```

Write to `<destination>.part`, stop after limit, decode with Pillow, call `image.verify()`, reopen and inspect dimensions, then atomically replace destination. SVG is accepted only if the installed decoder path can safely render it; otherwise return a clear unsupported-format error.

- [ ] **Step 4: Implement bounded LRU cache metadata**

Store files by SHA-256 of normalized URL and an atomic `index.json` containing size, access timestamp, content type, width, and height. On startup, remove missing/index-orphan entries. Never cache API credentials or complete request URLs containing credentials.

```python
class ImageCache:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.files = root / "files"
        self.index_path = root / "index.json"
        self.files.mkdir(parents=True, exist_ok=True)
        self.index = self._load_index()
        self.reconcile()

    @staticmethod
    def key_for(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        normalized = urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, "")
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def put(self, url: str, source: Path, metadata: DownloadedImage) -> Path:
        key = self.key_for(url)
        destination = self.files / key
        shutil.copyfile(source, destination)
        self.index[key] = {
            "size": destination.stat().st_size,
            "accessed_at": time.time(),
            "content_type": metadata.content_type,
            "width": metadata.width,
            "height": metadata.height,
        }
        self._evict()
        self._write_index()
        return destination

    def _write_index(self) -> None:
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.index, sort_keys=True), "utf-8")
        os.replace(temporary, self.index_path)

    def _evict(self) -> None:
        while sum(item["size"] for item in self.index.values()) > self.max_bytes:
            oldest = min(self.index, key=lambda key: self.index[key]["accessed_at"])
            (self.files / oldest).unlink(missing_ok=True)
            del self.index[oldest]
```

- [ ] **Step 5: Activate shared service and bridge functions**

`search_covers` decodes:

```json
{
  "mode":"public_books|general_image",
  "query":"",
  "isbn":"",
  "title":"",
  "author":"",
  "locale":"zh-TW",
  "max_results":20,
  "safe_search":true,
  "credential":{"api_key":"","search_engine_id":""}
}
```

Remove credential fields before serializing diagnostics or response. Android bridge exposes `cover_search_json` and `cover_download_candidate_json`.

- [ ] **Step 6: Run tests and commit**

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests/cover/search python-tests/cover/test_service.py -q
git add python/src/epub_a4_word/cover app/src/main/python/android_bridge.py python-tests
git commit -m "feat: validate and cache selected cover images"
```

Expected: PASS.

---
