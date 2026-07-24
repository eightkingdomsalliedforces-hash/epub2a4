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

## Plan Parts

1. [`2026-07-24-cover-core-export-part-1.md`](2026-07-24-cover-core-export-part-1.md) — Tasks 1–3.
2. [`2026-07-24-cover-core-export-part-2.md`](2026-07-24-cover-core-export-part-2.md) — Tasks 4–7.
3. [`2026-07-24-cover-core-export-part-3.md`](2026-07-24-cover-core-export-part-3.md) — Tasks 8–10.

Execute parts in order. Every part retains the approved constraints, exact file paths, TDD red/green commands, implementation snippets, verification commands, and commit checkpoints.
