# Desktop Cover Panel Regression Design

## Problem

The Windows Desktop cover page in v0.6.1 shows two independent
「出版社封底與書脊資訊」panels. At a typical 1200 × 800 window size, the right
sidebar can collapse until the source browse button lies outside the visible
viewport.

Runtime inspection confirms both failures:

- `CoverPage.findChildren(PublisherMetadataPanel)` returns two panels.
- The right viewport can be 54 px wide while the browse button begins at
  x = 314 px.

## Root Cause

`CoverSetupPanel` owns a `PublisherMetadataPanel`, but `CoverPage` creates a
second `PublisherMetadataPanel` and inserts it beneath the setup panel. The
duplicated wide form increases the sidebar's size pressure, while the splitter
allows the right pane to collapse without preserving space for the fixed-width
browse button.

## Design

`CoverSetupPanel.publisher_metadata_panel` becomes the sole publisher metadata
panel. `CoverPage.publisher_metadata_panel` remains as a compatibility alias to
that same object so existing controller wiring and tests keep one source of
truth. `CoverPage` must not add the aliased widget to the layout a second time.

The right scroll area receives a practical minimum width, and the source path
editor is allowed to shrink before the fixed-width browse button. This keeps
the button visible without introducing a horizontal scrollbar or removing
cover-editor space.

## Data Flow

Source inspection populates the sole panel through `CoverSetupPanel`. Before a
project exists, its values are included in `CoverSetupValues`. After project
creation, the same panel remains connected to the existing debounced metadata
update, Logo search, manual Logo selection, and Logo clearing handlers.

## Tests and Acceptance Criteria

- A `CoverPage` contains exactly one `PublisherMetadataPanel`.
- `CoverPage.publisher_metadata_panel` and
  `CoverPage.setup_panel.publisher_metadata_panel` are the same object.
- At 1200 × 800, the browse button is visible and its full rectangle lies
  inside the right scroll area's viewport.
- Existing publisher metadata, Logo, cover-page, and Desktop test suites pass.
- A Windows portable build passes its verification script.

## Release

After local and GitHub CI verification, merge the repair and publish v0.6.2
through the existing tag-triggered Release workflow.
