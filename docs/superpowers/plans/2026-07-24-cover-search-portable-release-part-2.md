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

## Part 2: Tasks 5–8


This part is divided into smaller executable documents to keep every task self-contained:

- [`2026-07-24-cover-search-portable-release-part-2a.md`](2026-07-24-cover-search-portable-release-part-2a.md) — Tasks 5–6.
- [`2026-07-24-cover-search-portable-release-part-2b.md`](2026-07-24-cover-search-portable-release-part-2b.md) — Tasks 7–8.

Execute the subparts in order.
