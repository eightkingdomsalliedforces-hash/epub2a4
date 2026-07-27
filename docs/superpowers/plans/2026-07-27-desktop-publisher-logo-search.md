# Desktop Publisher Logo Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let desktop users search publisher logos, inspect up to 20 ranked candidates, explicitly choose one, cache it, and embed the selected bytes into the cover project for offline export.

**Architecture:** Add a publisher catalogue and logo-specific candidate model in the shared search package. Adapters return normalized candidates from official domains, Wikimedia/Wikipedia, and generic public sources. A secure downloader validates bytes and a cache stores them; the desktop dialog only selects candidates and delegates persistence to the controller.

**Tech Stack:** Python standard library HTTP/JSON, Pillow, safe XML parsing, PySide6, pytest.

## Global Constraints

- Never generate or auto-select a logo.
- Initial result page is at most 20 unique candidates; `載入更多` requests another page of at most 20.
- Connection timeout 10 s, total timeout 30 s, at most 5 redirects, maximum 10 MiB.
- Only HTTP/HTTPS; validate decoded format and dimensions.
- Reject SVG scripts and external resources.
- Manual logos are never silently replaced.
- Export uses the embedded project copy and requires no network.

---

### Task 1: Publisher catalogue and candidate ranking

**Files:**
- Create: `python/src/epub_a4_word/cover/publisher_directory.py`
- Create: `python/src/epub_a4_word/cover/search/logo_models.py`
- Create: `python/src/epub_a4_word/cover/search/logo_ranking.py`
- Test: `python-tests/cover/test_publisher_logo_ranking.py`

**Interfaces:**
- Produces: `PublisherProfile`
- Produces: `LogoCandidate`
- Produces: `rank_logo_candidates(candidates, publisher) -> tuple[LogoCandidate, ...]`
- Produces: `dedupe_logo_candidates(...)`

- [ ] Write ranking, official-domain, transparency, format, and dedupe tests.
- [ ] Confirm RED.
- [ ] Implement catalogue, model, deterministic score, and stable dedupe key.
- [ ] Confirm GREEN.
- [ ] Commit `feat: add publisher logo candidate ranking`.

### Task 2: Search adapters and pagination

**Files:**
- Create: `python/src/epub_a4_word/cover/search/publisher_logo.py`
- Modify: `python/src/epub_a4_word/cover/search/http.py`
- Test: `python-tests/cover/test_publisher_logo_search.py`

**Interfaces:**
- Produces: `PublisherLogoSearch.search(query, page_token=None, limit=20) -> LogoSearchPage`
- Produces: official-site discovery, Wikimedia Commons API search, Wikipedia page-image fallback, and generic image-source adapter interface.

- [ ] Write mocked HTTP tests for source labels, pagination, and 20-result limits.
- [ ] Confirm RED.
- [ ] Implement adapters without scraping authenticated or blocked pages.
- [ ] Confirm GREEN.
- [ ] Commit `feat: search publisher logo sources`.

### Task 3: Secure download, cache, and project embedding

**Files:**
- Create: `python/src/epub_a4_word/cover/search/logo_download.py`
- Create: `python/src/epub_a4_word/cover/search/logo_cache.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Test: `python-tests/cover/test_publisher_logo_download.py`
- Test: `desktop/tests/test_publisher_logo_embedding.py`

**Interfaces:**
- Produces: `download_logo(candidate, destination_dir) -> DownloadedLogo`
- Produces: `LogoCache.get/put`
- Produces controller method: `apply_publisher_logo(downloaded, source_metadata)`

- [ ] Write tests for size, timeout, redirect, signature, SVG active-content rejection, cache reuse, and offline reopen.
- [ ] Confirm RED.
- [ ] Implement secure downloader and cache.
- [ ] Embed selected bytes into the project working directory and save `LogoAssetMetadata`.
- [ ] Confirm GREEN.
- [ ] Commit `feat: securely cache publisher logos`.

### Task 4: Candidate dialog and panel integration

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/publisher_logo_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/cover/publisher_metadata_panel.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `desktop/tests/test_publisher_logo_dialog.py`

**Interfaces:**
- Produces dialog methods: `set_page(page)`, `selected_candidate()`
- Produces signals: `candidate_confirmed(object)`, `load_more_requested(object)`, `manual_file_requested()`

- [ ] Write Qt tests for candidate cards, source badges, explicit selection, no auto-selection, and load-more.
- [ ] Confirm RED.
- [ ] Implement dialog and asynchronous search/download integration.
- [ ] Add manual image selection and `不使用 Logo` action.
- [ ] Confirm GREEN.
- [ ] Commit `feat: add publisher logo candidate dialog`.
