# Desktop PySide6 Cover Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default desktop Tkinter interface with a portable PySide6 application that preserves all existing conversion features and adds a full visual cover editor on Windows, macOS, and Linux.

**Architecture:** Build a thin desktop package around the shared `epub_a4_word` core. A main window owns navigation; conversion and cover workflows use separate controllers and pages. The cover canvas uses millimetres as scene coordinates, so zoom is presentation-only and cannot change export geometry.

**Tech Stack:** Python 3.13, PySide6 6.11.1, pytest, pytest-qt, Pillow, shared cover service, `QGraphicsScene`, `QUndoStack`, `QThreadPool`.

## Global Constraints

- This plan begins only after `2026-07-24-cover-core-export.md` passes its full test gate.
- PySide6 is the default GUI on Windows, macOS, and Linux.
- `--legacy-gui` opens a Tkinter compatibility window for one release only.
- The conversion workflow retains EPUB → A4 four-up/A6 signature/A5/4×6 and DOCX → A5/4×6 behavior.
- The cover tool accepts EPUB, DOCX, and PDF independently and can also receive actual page count and trim size from a completed conversion.
- Cover edits remain in `CoverProject` schema version `1`; desktop-specific state must not be written into project geometry.
- Scene coordinates, inspector values, and serialized positions use millimetres.
- Preview may be reduced resolution; PDF/DOCX export always delegates to the shared core.
- The desktop app performs no update check.
- Search UI is added by the later search/release plan; this plan supports EPUB-embedded and local images.

---

## Part 2: Tasks 4–7

This part is divided into smaller executable documents to keep every task self-contained:

- [`2026-07-24-desktop-pyside6-cover-editor-part-2a.md`](2026-07-24-desktop-pyside6-cover-editor-part-2a.md) — Tasks 4–5.
- [`2026-07-24-desktop-pyside6-cover-editor-part-2b.md`](2026-07-24-desktop-pyside6-cover-editor-part-2b.md) — Tasks 6–7.

Execute the subparts in order.
