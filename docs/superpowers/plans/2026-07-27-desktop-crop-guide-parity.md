# Desktop Crop Guide Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the desktop converter use one crop/fold checkbox and show the same shared guide geometry in its preview and exported DOCX, including full B6-on-A5 cut lines.

**Architecture:** Replace the B6-only mark combo with one checkbox and one advanced compatibility checkbox. A generic preview widget consumes `build_page_placement(LayoutSettings)`. `LayoutSettings.guide_render_mode` selects VML or page-anchored DrawingML while coordinates remain shared.

**Tech Stack:** Python 3.13, PySide6, python-docx OOXML, pytest, LibreOffice render smoke.

## Global Constraints

- B6-on-A5 content remains `(20,28,128,182)` on A5.
- B6 guides are full lines `(0,28)->(148,28)` and `(20,0)->(20,210)`.
- Four-up has one solid internal vertical and horizontal crop line.
- Signature roles remain distinct; folds are dashed and cuts are solid.
- Single A5 and single 4x6 emit no internal guides and show `紙張邊緣即成品邊`.
- VML and DrawingML use identical `CropGuide` coordinates and `0.35 pt` default width.

---

### Task 1: Unify desktop request settings

**Files:**
- Modify: `python/src/epub_a4_word_desktop/pages/converter_page.py`
- Modify: `python/src/epub_a4_word_desktop/conversion/models.py`
- Modify: `python/src/epub_a4_word/pagination.py`
- Test: `desktop/tests/test_converter_crop_controls.py`
- Test: `python-tests/core/test_pagination.py`

**Interfaces:**
- Produces: `guide_render_mode: Literal["vml", "drawingml"] = "vml"`
- `cut_guides` is the only on/off control for every supported mode.
- B6 maps `cut_guides=True` to `output_mark_mode="crop_marks"` at the shared settings boundary.

- [ ] Write failing UI and request tests.
- [ ] Confirm RED.
- [ ] Remove the B6-only mark combo and add `高相容裁切線`.
- [ ] Normalize settings consistently for B6 and non-B6 modes.
- [ ] Confirm GREEN.
- [ ] Commit `fix: unify desktop crop guide controls`.

### Task 2: Generic shared-geometry preview

**Files:**
- Replace: `python/src/epub_a4_word_desktop/conversion/layout_preview.py`
- Modify: `python/src/epub_a4_word_desktop/pages/converter_page.py`
- Test: `desktop/tests/test_layout_preview.py`

**Interfaces:**
- Produces: `LayoutPreview.set_settings(settings: LayoutSettings)`
- Consumes: `build_page_placement(settings)` and `CropGuide.role`

- [ ] Write tests that inspect preview geometry for B6, four-up, signature, and single-page modes.
- [ ] Confirm RED.
- [ ] Implement generic paper/content/guide drawing and finished-edge message.
- [ ] Confirm GREEN.
- [ ] Commit `feat: preview shared crop guide geometry`.

### Task 3: DrawingML compatibility renderer

**Files:**
- Modify: `python/src/epub_a4_word/crop_marks.py`
- Modify: `python/src/epub_a4_word/docx_writer.py`
- Modify: `python/src/epub_a4_word/word_reflow.py`
- Test: `python-tests/test_docx_page_guides.py`
- Test: `python-tests/test_drawingml_page_guides.py`

**Interfaces:**
- Produces: `add_page_guides(header, placement, render_mode="vml")`
- VML and DrawingML branches consume the same `placement.guides` sequence.

- [ ] Write failing XML parity tests for both renderers.
- [ ] Confirm RED.
- [ ] Implement page-anchored DrawingML line shapes with solid/dashed role styling.
- [ ] Thread `guide_render_mode` through EPUB and DOCX output paths.
- [ ] Confirm GREEN.
- [ ] Commit `feat: add DrawingML crop guide renderer`.

### Task 4: Full regression and rendered verification

**Files:**
- Modify: `scripts/inspect_cover_exports.py` only if needed for guide inspection
- Test: existing shared and desktop suites

- [ ] Run focused crop-guide tests.
- [ ] Run all shared tests.
- [ ] Run all desktop tests offscreen.
- [ ] Render B6, four-up, and signature DOCX files through LibreOffice and inspect output.
- [ ] Run compile and structure verification.
- [ ] Commit any test-only corrections with `test: verify desktop crop guide parity`.
