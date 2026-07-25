# Changelog

## Unreleased

### Desktop PySide6 cover editor

- Added `epub2a4-desktop` with PySide6 as the default interface and a temporary `--legacy-gui` Tkinter compatibility path.
- Preserved the existing EPUB and DOCX conversion modes with background progress, cancellation, warnings, and conversion-to-cover handoff.
- Added HOME, CONVERTER, and COVER routes in a `QStackedWidget` main window.
- Added a millimetre-based `QGraphicsScene` cover canvas with guides, zoom, selectable elements, exact transforms, undo, and redo.
- Added setup, template, local/EPUB artwork, crop, layer, and element-inspector controls.
- Added portable `.cover.json` project bundles with SHA-256-deduplicated relative image assets.
- Added background, transaction-style independent PDF and DOCX export with output validation and rollback protection.
- Added Linux, Windows, and macOS Python 3.13 GitHub Actions coverage with an offscreen end-to-end desktop smoke gate.

### Shared cover core

- Completed the shared CoverProject schema, metadata inspection, cover geometry, templates, Pillow rendering, exact A4 PDF export, editable DOCX export, unified service API, Android JSON bridge, and golden structural QA tooling.

### Known limitations

- Online image search, Android cover-editor UI, and desktop release packaging are intentionally deferred to later plans.
- PDF is the print reference; Word and LibreOffice can render floating text boxes and substituted fonts slightly differently.
