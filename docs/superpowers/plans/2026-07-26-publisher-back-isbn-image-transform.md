# Publisher Back Cover, ISBN Writeback, and Image Transform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a publisher-style back-cover template, validated ISBN writeback, and shared interactive image transforms.

**Architecture:** Keep project schema v1 and extend optional metadata/content fields. Put ISBN validation and EAN rendering in shared core modules, update templates and the desktop application through existing controller/patch interfaces, and make Pillow plus Qt use the same fit/scale/offset/crop semantics.

**Tech Stack:** Python 3.13, dataclasses, Pillow, PySide6, pytest, pytest-qt.

## Global Constraints

- Do not generate images or add new search providers.
- Preserve old schema-v1 projects and legacy crop keys.
- Existing project ISBN may never be overwritten without confirmation.
- PDF and DOCX remain based on the shared Pillow spread renderer.
- Central publisher logo is optional; no placeholder image or text is rendered.

---

### Task 1: ISBN primitives and candidate identifiers

**Files:**
- Create: `python/src/epub_a4_word/cover/isbn.py`
- Modify: `python/src/epub_a4_word/cover/search/models.py`
- Modify: `python/src/epub_a4_word/cover/search/google_books.py`
- Test: `python-tests/cover/test_isbn.py`
- Test: `python-tests/cover/test_google_books.py`

- [ ] Add failing tests for ISBN-10/13 checksum validation, ISBN-13 preference, UUID rejection, and preservation of both Google Books identifiers.
- [ ] Run focused tests and confirm failures are caused by missing APIs/fields.
- [ ] Implement `normalize_isbn`, `valid_isbns`, `preferred_isbn`, and SearchCandidate `isbns` serialization.
- [ ] Re-run focused tests.

### Task 2: Publisher back-cover template and barcode rendering

**Files:**
- Modify: `python/src/epub_a4_word/cover/models.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `python-tests/cover/test_templates.py`
- Test: `python-tests/cover/test_render.py`

- [ ] Add failing tests for template catalog entry, non-empty-field-only elements, central logo slot, valid EAN bars, and no invalid ISBN placeholder.
- [ ] Run focused tests and confirm expected failures.
- [ ] Add optional metadata fields, template builder, EAN-13 renderer with optional 2/5 digit add-on, and desktop template menu entry.
- [ ] Re-run focused tests.

### Task 3: ISBN application policy and barcode synchronization

**Files:**
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Modify: `python/src/epub_a4_word_desktop/cover/search_panel.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `desktop/tests/test_cover_page.py`
- Test: `desktop/tests/test_cover_search_free_sources.py`

- [ ] Add failing tests for candidate ISBN display, auto-apply on unique high-confidence same-volume match, confirmation on conflict, and barcode text synchronization.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement controller metadata update and page-level decision flow before image download.
- [ ] Re-run focused tests.

### Task 4: Shared image transform rendering

**Files:**
- Modify: `python/src/epub_a4_word/cover/render.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`
- Test: `python-tests/cover/test_render.py`

- [ ] Add failing pixel tests for fit, scale, offset, crop, and legacy crop fields.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement one normalized transform algorithm in Pillow and equivalent Qt painting.
- [ ] Re-run focused tests.

### Task 5: Desktop controls and direct manipulation

**Files:**
- Modify: `python/src/epub_a4_word_desktop/cover/inspector.py`
- Modify: `python/src/epub_a4_word_desktop/cover/canvas.py`
- Modify: `python/src/epub_a4_word_desktop/cover/items.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `desktop/tests/test_cover_page.py`
- Test: `desktop/tests/test_cover_canvas.py`

- [ ] Add failing pytest-qt tests for 10–500% slider, fit/fill/original/center/reset actions, image wheel zoom, and Shift/Alt corner-resize commits.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement controls and signals using the existing undoable controller patch path.
- [ ] Re-run focused tests.

### Task 6: Full verification and documentation

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `BUILD_STATUS.md`

- [ ] Run `python3.13 -m pytest python-tests desktop/tests -q`.
- [ ] Run `python3.13 -m compileall python/src desktop/tests python-tests`.
- [ ] Run `python3.13 scripts/verify_project.py`.
- [ ] Run `git diff --check`.
- [ ] Record exact verification results and open a draft pull request.
