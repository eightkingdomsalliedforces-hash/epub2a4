# Restore Complete Publisher Metadata Design

## Goal

Restore the complete publisher-cover metadata workflow from PR #13 on top of
the current `main`, while preserving the publisher Logo, vertical spine,
source-browse, and tag-driven Release fixes delivered by PR #14.

The repaired release will be published as `v0.6.1` after the integration PR
passes all Desktop, shared Python, Android, and Windows portable checks.

## Required Publisher Fields

The shared project schema, Desktop editor, and Android editor must retain and
round-trip these publisher fields:

- ISBN and ISBN add-on
- Publisher and price
- Publication or agency information
- Translator
- English title or subtitle
- Volume or book count
- Volume or chapter number
- Series name
- Internal book code
- Spine accent color

Empty optional fields must remain omitted from rendered back-cover and spine
content instead of producing placeholder labels.

## Integration Strategy

Create `fix/restore-complete-publisher-metadata` from the current `main` and
merge the head of PR #13 (`fix/reference-back-cover-isbn-clarity`) into it.
Resolve the fifteen overlapping files according to ownership rather than
choosing one entire side.

PR #13 owns:

- expanded shared and Android metadata models;
- JSON serialization and backward-compatible defaults;
- Desktop publisher metadata panel and field validation;
- publisher Logo search, download, ranking, embedding, and replacement flow;
- publisher information and spine-layout helpers;
- Android metadata editing and project handoff.

Current `main` from PR #14 owns:

- the `v*` tag-driven `.github/workflows/release.yml`;
- publisher Logo region clipping in `front_only` projects;
- actual per-character CJK vertical text rendering;
- reference-sized spine title, author, publisher, and top Logo placement;
- the non-collapsing Desktop source browse button;
- the single-instance publisher back-cover and spine elements.

Where both branches implement the same behavior differently, retain PR #13's
complete metadata architecture and adapt PR #14's rendering and usability
regressions to that architecture.

## Data Flow

Desktop and Android editors write the same schema-v1 metadata keys. Shared
project loading supplies empty-string defaults for older projects. Metadata
updates refresh text and barcode content without resetting user-adjusted
element geometry unless the user explicitly resets the template.

The publisher template consumes the shared metadata model to build:

- one back-cover ISBN and publisher-information group;
- one central publisher Logo;
- one spine Logo;
- vertical title, volume, author, publisher, and internal-code slots selected
  according to available spine width.

Logo images are copied or downloaded into project assets and rendered with
`contain`. Template Logos explicitly clip to their BACK or SPINE region so
`front_only` image mode cannot hide them.

## UI Behavior

The Desktop editor displays exactly one publisher metadata panel. Its source
browse button remains visible at supported window sizes. Logo controls support
search, manual selection, replacement, and explicit omission.

The Android editor exposes the same publisher fields required for project
round-tripping and provides browser search plus local Logo selection. Both
platforms show field-specific validation errors for malformed ISBN add-ons and
spine colors.

## Conflict and Error Handling

- Existing schema-v1 projects without the expanded fields load with empty
  defaults.
- Invalid optional fields block metadata application and identify the affected
  field.
- Missing Logo files produce a rendering error instead of silently exporting
  an incomplete cover.
- Network search failure does not prevent manual Logo selection.
- Reapplying or refreshing the publisher template must not duplicate standard
  elements or the publisher metadata panel.

## Verification

Add or retain regression tests proving:

- every required field survives JSON save and reload on shared Python and
  Android;
- Desktop shows one metadata panel and keeps the source browse button visible;
- Logo search/manual selection replaces rather than duplicates Logo elements;
- Logos render on BACK and SPINE in `front_only` mode;
- CJK spine text is vertical and uses the reference-sized typography;
- empty fields do not emit placeholder text;
- existing user geometry survives metadata refresh.

Run the complete shared Python and Desktop PySide6 suites, Android unit tests
and debug APK assembly, project verification, Windows portable build and smoke
test, and the tag Release workflow contract check.

## Delivery

Push the repair branch and open a PR against `main`. After all CI checks pass,
squash-merge the PR, tag the resulting `main` commit as `v0.6.1`, and verify
the GitHub Release contains:

- `EPUB2A4-Windows-Portable-x64.zip`
- `EPUB2A4-Android.apk`
- `SHA256SUMS.txt`
