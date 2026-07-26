# Changelog

## Unreleased

### Conversion and pagination

- Changed EPUB conversion to default to body-only output, with a user-visible option to retain the original front and back cover pages.
- Added the body-only control to both the PySide6 desktop converter and the Android converter.
- Added a shared EPUB structure inspector for OPF, manifest, spine, guide, landmarks, front-cover and back-cover roles.
- Prevented ordinary final illustrations and text pages from being silently classified as back covers.
- Reworked A5, 4×6, and B6-on-A5 single-page DOCX output to use one top-level table with one exact-height non-splittable row per physical page.
- Added rendered PDF regressions requiring N source pages to produce N physical pages with no leading, interstitial, or trailing blank pages.
- Added exact size checks for A5 at 148 × 210 mm and 4×6 at 101.6 × 152.4 mm.

### Embedded cover handling

- Added direct extraction of separate EPUB front and back cover images.
- Added explicit confirmation before a medium-confidence final image can be used as the back cover.
- Kept front and back assets as separate editable project elements.
- Changed the default source-cover template to avoid generated title, description, publisher, spine, and barcode elements.

### Free multilingual cover lookup

- Changed Google Books credentials to require only an API Key and removed Search Engine ID from the active workflow.
- Preserved read compatibility with legacy credential files containing `search_engine_id`.
- Kept Open Library as an independently switchable no-key source.
- Added Project Gutenberg cover candidates through the free Gutendex API.
- Added conservative title normalization, volume extraction, ISBN-10/ISBN-13 validation, and ordered query planning.
- Added Wikidata multilingual alias and ISBN resolution for translated titles.
- Added safeguards against author, volume, and media-type mismatches.
- Added a local confirmed-alias cache which can reuse series aliases but never reuses an old volume ISBN for a new volume.
- Added independent provider warnings so one failed or rate-limited source does not discard successful candidates from other sources.
- Removed Google Custom Search from the active desktop cover-search UI.

### Desktop and packaging

- Added Google Books, Open Library, and Project Gutenberg source switches.
- Added an optional original-title or formal-alias field and visible resolved aliases/ISBNs.
- Added a clear-alias-cache action.
- Added Windows, macOS, and Linux desktop coverage for the new controls.
- Added source-layout checks for the EPUB structure and free multilingual search modules.
- Updated Windows portable focused tests to cover single-page output and the new search pipeline.

### Known limitations

- Microsoft Word pagination and print positioning still require final real-device validation on the user's Windows installation even though OOXML and LibreOffice/PDF regressions pass.
- Open Library, Google Books, Wikidata, and Gutendex can still be unavailable or rate-limited by their operators; failures are isolated and reported by source.
- Project Gutenberg coverage is strongest for public-domain books and is not expected to find most modern light novels or commercial books.
- PDF remains the cover print reference; Word and LibreOffice may render floating text boxes, substituted fonts, and VML crop marks slightly differently.
- Existing DOCX and `.cover.json` files are not rewritten automatically and must be regenerated to receive the new behavior.
