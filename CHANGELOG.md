# Changelog

## Unreleased

### Added

- PySide6 desktop application with HOME、CONVERTER、COVER routing.
- Complete EPUB／DOCX conversion workflow with progress, cancellation, warnings, and direct cover handoff.
- Millimetre-based full-cover canvas, guides, zoom, selection, undo/redo, setup, inspector, templates, and layers.
- Local and EPUB-embedded artwork import with size validation and normalized crop controls.
- Portable `.cover.json` project bundles with relative, SHA-256-deduplicated assets.
- Transactional 200／300 DPI PDF and editable DOCX cover export.
- Cross-platform offscreen smoke gate on Ubuntu、Windows、macOS with Python 3.13 and PySide6 6.11.1.

### Compatibility

- `epub2a4-desktop` starts PySide6 by default.
- `epub2a4-desktop --legacy-gui` retains the Tkinter interface for one compatibility release.
- Online image search is intentionally not included in this desktop implementation plan.
