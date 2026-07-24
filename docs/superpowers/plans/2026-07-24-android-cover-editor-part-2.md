# Android Compose Cover Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Android cover workflow which opens EPUB/DOCX/PDF, confirms physical book settings, applies a local template, permits touch-based fine tuning, and saves independent PDF plus DOCX files.

**Architecture:** Keep Kotlin/Compose responsible for route state, SAF access, touch gestures, forms, and local credential ownership. Call the shared Python cover service through a dedicated gateway which exchanges schema-versioned JSON and runs export/render operations on the existing large-stack execution mechanism.

**Tech Stack:** Kotlin/JVM 17, Jetpack Compose Material 3, Android API 24+, Chaquopy Python 3.13, StateFlow, SAF/DocumentsContract, JUnit 4, Compose UI tests.

## Global Constraints

- This plan begins only after `2026-07-24-cover-core-export.md` passes.
- Minimum Android version stays API 24 and ABI stays arm64-v8a.
- Conversion remains available while the cover tool is added.
- Cover tool inputs: EPUB, DOCX, PDF.
- Online search is not implemented in this plan; EPUB-embedded and local images work offline.
- Android does not generate artwork.
- Project JSON remains schema version `1` and all geometry values are millimetres.
- Page count must be explicitly confirmed before creating or exporting a cover.
- Default bleed is 3 mm, overlap is fixed at 5 mm.
- The app creates two independent files in a user-selected SAF directory.
- Export defaults to 300 DPI and offers an explicit 200 DPI low-memory choice; it never silently lowers DPI.
- Python render/export work must not run on the main thread or a small coroutine worker stack.
- Until the later search plan, the manifest still contains no `INTERNET` permission.

---

## Part 2: Tasks 5–8

This part is divided into smaller executable documents to keep every task self-contained:

- [`2026-07-24-android-cover-editor-part-2a.md`](2026-07-24-android-cover-editor-part-2a.md) — Tasks 5–6.
- [`2026-07-24-android-cover-editor-part-2b.md`](2026-07-24-android-cover-editor-part-2b.md) — Tasks 7–8.

Execute the subparts in order.
