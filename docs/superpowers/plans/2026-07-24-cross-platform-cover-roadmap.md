# Cross-Platform Full-Cover Tool Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an independent full-cover creator for Android, Windows, macOS, and Linux which lays out `back cover | spine | front cover`, supports local and searched artwork, and exports PDF plus editable DOCX.

**Architecture:** Keep one canonical Python core under `python/src/epub_a4_word`, package it into Android through Chaquopy source sets, and import it directly from the PySide6 desktop application. Android Compose and desktop PySide6 own interaction and preview state; the shared core owns metadata, project JSON, geometry, templates, rendering, exports, and search-provider response normalization.

**Tech Stack:** Python 3.13, Pillow 11.0.0, python-docx 1.1.2, lxml 5.3.0, pypdf 6.14.2, pytest; Kotlin/JVM 17, Jetpack Compose, Chaquopy, Coil 3.5.0; PySide6 6.11.1, keyring 25.7.0, platformdirs 4.10.1, PyInstaller, AppImage tooling.

## Global Constraints

- Supported platforms: Android 7.0/API 24+ arm64-v8a, Windows, macOS, and Linux.
- The program must not generate artwork with AI.
- Cover order is always `back | spine | front`.
- Supported trim sizes are A5 `148 × 210 mm`, A6 `105 × 148 mm`, and 4×6 inch `101.6 × 152.4 mm`.
- Default bleed is `3 mm`, configurable from `0` through `10 mm`.
- Automatic spine width is `ceil(page_count / 2) × paper_caliper_mm`; the user may override paper caliper or final spine width.
- Default paper estimates are 70 gsm `0.09 mm`, 80 gsm `0.10 mm`, 100 gsm `0.12 mm`, and 120 gsm `0.14 mm`.
- Never scale the finished cover merely to fit A4.
- A cover which fits A4 at 1:1 exports as one A4 page; otherwise export back, spine, and front as three A4 pages with `5 mm` overlap, crop marks, and assembly marks.
- Cover exports are always independent files and never modify the body document.
- Output names are `<title>_完整書封.pdf` and `<title>_完整書封.docx`.
- PDF is the print reference; DOCX keeps principal text and image objects editable.
- Android and desktop must consume the same `CoverProject` schema and shared geometry implementation.
- Network access occurs only after an explicit user search action; source documents are never uploaded.
- General image search uses user-supplied Google API Key and Search Engine ID; no shared credential is embedded.
- Desktop releases are portable: Windows ZIP, macOS `.app.zip`, Linux AppImage; there is no automatic update check.
- PySide6 is the default desktop UI; `--legacy-gui` remains available for one release only.

---

## Plan Set and Dependency Order

1. `2026-07-24-cover-core-export.md`
   - Canonical Python source layout.
   - `CoverProject` schema, metadata, geometry, templates, render pipeline, PDF and editable DOCX export.
   - Android JSON bridge functions.
   - This plan must finish first.

2. `2026-07-24-desktop-pyside6-cover-editor.md`
   - PySide6 application shell and migration of existing conversion workflow.
   - Desktop visual cover editor, inspectors, local assets, export workflow, and one-release Tkinter fallback.
   - Depends on plan 1 only.

3. `2026-07-24-android-cover-editor.md`
   - Compose navigation, cover setup/editor screens, gestures, metadata flow, preview, SAF export, and conversion-completion entry.
   - Depends on plan 1 only and may run in parallel with plan 2.

4. `2026-07-24-cover-search-portable-release.md`
   - Google Books, Open Library, Google Custom Search, credentials, image cache, source/licensing UI, portable paths, packaging, and release CI.
   - Depends on plans 1–3.

## Cross-Plan Interface Contract

The following names are frozen before UI work begins:

| Function | Exact signature |
|---|---|
| Inspect source | `inspect_source(source_path: str) -> dict[str, object]` |
| Create project | `new_project(source_path: str, settings_json: str) -> str` |
| Apply template | `apply_template(project_json: str, template_id: str) -> str` |
| Render preview | `render_preview(project_json: str, output_png: str, max_px: int = 1600) -> dict[str, object]` |
| Export pair | `export_cover(project_json: str, pdf_path: str, docx_path: str, dpi: int = 300) -> dict[str, object]` |
| Search | `search_covers(request_json: str) -> str` |
| Download candidate | `download_candidate(candidate_json: str, destination_path: str) -> dict[str, object]` |

```text
CoverProject.schema_version = 1
All geometry values are decimal millimetres.
All project JSON is UTF-8 and uses snake_case property names.
Image files are referenced by absolute working-copy path, never embedded as base64.
```

Android calls these functions through `app/src/main/python/android_bridge.py`. Desktop imports them directly.

## Integration Gates

- [ ] **Gate 1 — Core:** `PYTHONPATH=python/src python3.13 -m pytest python-tests -q` reports zero failures and generated PDF/DOCX fixtures pass structural inspection.
- [ ] **Gate 2 — Desktop:** `python -m pytest desktop/tests -q` passes; PySide6 conversion and cover flows start on all three desktop CI runners.
- [ ] **Gate 3 — Android:** `gradle --no-daemon testDebugUnitTest assembleDebug` passes; instrumented editor tests pass on API 24 and a current API emulator or device.
- [ ] **Gate 4 — Search:** provider fixture tests pass without network; opt-in live smoke tests pass with repository secrets.
- [ ] **Gate 5 — Release:** Windows ZIP, macOS `.app.zip`, Linux AppImage, and Android APK launch and export the same golden `CoverProject` within `0.1 mm` geometry tolerance.

## Final Acceptance Run

Use a single fixture project with A5 trim, 160 pages, 80 gsm paper, 3 mm bleed, and a full-spread background.

```bash
PYTHONPATH=python/src python3.13 -m pytest python-tests desktop/tests -q
gradle --no-daemon testDebugUnitTest assembleDebug
python3.13 scripts/compare_cover_geometry.py \
  build/golden/desktop-result.json \
  build/golden/android-result.json \
  --tolerance-mm 0.1
```

Expected results:

```text
Python tests: PASS
Desktop tests: PASS
Android unit tests: PASS
Android debug APK: CREATED
Geometry comparison: PASS; maximum delta <= 0.1 mm
```
