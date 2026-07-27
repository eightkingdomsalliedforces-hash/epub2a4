# Windows portable verification

The Windows portable build must include and smoke-test the desktop publisher workflow introduced in PR #13:

- shared publisher metadata editor in setup and cover editor;
- `publisher_back_matter` backward-compatible alias for the combined publisher back-cover and vertical-spine template;
- publisher logo candidate download, safe project embedding, and Qt SVG rasterization;
- desktop B6-on-A5 crop-guide controls and shared-geometry preview;
- offline startup of the packaged executable.

The GitHub Actions workflow under `.github/workflows/windows-portable.yml` is the source of truth for the current PyInstaller build and packaged-executable smoke checks.
