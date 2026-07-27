# Desktop Publisher Metadata and Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one reusable desktop publisher metadata editor and a combined publisher back-cover plus vertical spine template which preserves user-adjusted geometry during metadata updates.

**Architecture:** Extend schema-v1 with optional publisher/spine fields and a serializable logo metadata record. Build one `PublisherMetadataPanel` used by both setup and editor. Template generation uses stable element IDs and a merge-by-ID refresh function so content changes do not reset transforms, opacity, rotation, or z-order.

**Tech Stack:** Python 3.13, dataclasses, PySide6, Pillow, pytest, pytest-qt.

## Global Constraints

- Keep `schema_version=1`; all new fields default to empty values.
- Canonical template ID is `publisher_back_matter_with_spine`; `publisher_back_matter` is an alias.
- Debounce editor metadata changes for exactly 300 ms.
- Preserve user-created elements and existing transforms during metadata refresh.
- Do not generate images or bundle commercial fonts.
- `DFPYuanW5-GB` and `DFPYuanW3-GB` remain the first publisher font candidates.

---

### Task 1: Extend schema-v1 publisher and spine metadata

**Files:**
- Modify: `python/src/epub_a4_word/cover/models.py`
- Modify: `python/src/epub_a4_word/cover/project_io.py`
- Modify: `python/src/epub_a4_word/cover/service.py`
- Test: `python-tests/cover/test_publisher_spine_metadata.py`

**Interfaces:**
- Produces: `LogoAssetMetadata`
- Produces fields on `CoverMetadata`: `publisher_id`, `english_title`, `volume_number`, `arc_label`, `series_name`, `internal_book_code`, `spine_accent_color`, `publisher_logo`
- Produces: `metadata_overrides_from_settings(settings) -> dict[str, object]`

- [ ] Write failing round-trip and old-schema tests.
- [ ] Run `python -m pytest python-tests/cover/test_publisher_spine_metadata.py -q` and confirm RED.
- [ ] Add dataclass fields, validation, JSON reconstruction, and optional settings overrides.
- [ ] Run the focused tests and confirm GREEN.
- [ ] Commit `feat: extend publisher spine metadata`.

### Task 2: Create reusable `PublisherMetadataPanel`

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/publisher_metadata_panel.py`
- Modify: `python/src/epub_a4_word_desktop/cover/setup_panel.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `desktop/tests/test_publisher_metadata_panel.py`

**Interfaces:**
- Produces: `PublisherMetadataValues`
- Produces signals: `values_changed(object)`, `search_logo_requested(str)`, `manual_logo_requested()`
- Produces methods: `set_values(...)`, `values()`, `set_validation_error(field, message)`

- [ ] Write failing tests proving setup and editor use the same widget class and field definitions.
- [ ] Confirm RED.
- [ ] Implement fields, validation, trim/normalization, and field-level errors.
- [ ] Replace the setup-only translator row with the shared panel.
- [ ] Add the same panel to the editor side and a 300 ms single-shot timer.
- [ ] Confirm focused desktop tests GREEN.
- [ ] Commit `feat: add shared publisher metadata panel`.

### Task 3: Combined template and three spine-width layouts

**Files:**
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Create: `python/src/epub_a4_word/cover/spine_layout.py`
- Test: `python-tests/cover/test_publisher_spine_template.py`

**Interfaces:**
- Produces: `SpineLayoutTier = Literal["full", "compact", "minimal"]`
- Produces: `build_spine_elements(project, layout) -> tuple[CoverElement, ...]`
- Stable IDs: `spine-publisher-logo`, `spine-title-main`, `spine-title-english`, `spine-volume`, `spine-arc`, `spine-author`, `spine-internal-code`, `spine-publisher-name`, `spine-background`

- [ ] Write failing tests for alias canonicalization and the `>=10`, `6..<10`, `<6` breakpoints.
- [ ] Confirm RED.
- [ ] Implement deterministic layout tiers and white spine background.
- [ ] Make both template IDs produce the combined template while saving the canonical ID.
- [ ] Confirm GREEN.
- [ ] Commit `feat: add publisher spine template`.

### Task 4: Refresh template-managed content without resetting geometry

**Files:**
- Modify: `python/src/epub_a4_word/cover/templates.py`
- Modify: `python/src/epub_a4_word_desktop/cover/controller.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Test: `python-tests/cover/test_template_metadata_refresh.py`
- Test: `desktop/tests/test_publisher_metadata_refresh.py`

**Interfaces:**
- Produces: `refresh_template_metadata(project, metadata) -> CoverProject`
- Produces controller method: `update_metadata(patch: Mapping[str, object], *, reset_layout: bool = False)`

- [ ] Write tests that move/resize template elements, update metadata, and assert transforms remain unchanged.
- [ ] Confirm RED.
- [ ] Implement merge-by-stable-ID and hidden-empty-element behavior.
- [ ] Connect editor debounce to `controller.update_metadata`.
- [ ] Add explicit `重設模板版面` action.
- [ ] Confirm focused and regression tests GREEN.
- [ ] Commit `feat: preserve publisher template geometry`.
