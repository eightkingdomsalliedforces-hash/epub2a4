# Windows Cover Search and B6-on-A5 EPUB Conversion Design

**Status:** Approved

## Goal

Complete the Windows cover workflow and add a new EPUB conversion layout where the book is reflowed as B6 content on physical A5 pages.

The cover workflow searches only for existing images. It does not generate images with AI or any other image-generation service.

## Scope

This design contains two independent modules:

1. Windows cover discovery, classification, selection, and composition.
2. EPUB reflow to a B6 content area centered on an A5 Word page, with optional crop marks.

The modules may share document metadata, but their conversion and UI state must remain separate.

---

## Module 1: Windows Cover Discovery and Composition

### Entry behavior

When the user opens an EPUB, DOCX, or PDF in the Windows cover tool:

1. Extract available ISBN, title, author, and embedded cover images.
2. Show embedded cover images immediately.
3. Start a background public-book search using Google Books and Open Library.
4. If Google image-search credentials are already stored, also start searches for front cover, back cover, spine, full spread, and reference photographs.
5. If credentials are absent, do not interrupt the user with a modal dialog. Show a visible `設定圖片搜尋` action instead.

Searches never auto-apply a result and never select the first candidate without user action.

### Search sources

Public-book search uses:

- Google Books
- Open Library

General image search uses Google Custom Search image mode with a user-supplied API Key and Search Engine ID.

The application must not scrape Google Images result pages. Credentials must not be bundled in source code, the executable, logs, diagnostics, fixtures, or crash reports.

### Search order and fallback

1. Query public-book databases by ISBN when available.
2. Query public-book databases by title and author.
3. Show all normalized public-book candidates.
4. General image search runs automatically only when credentials are already stored.
5. Without credentials, general image search remains a manual action after the user configures it.
6. A failed network search must not disable embedded-image or local-image workflows.

### General-image queries

General search should issue distinct queries for:

- front cover
- back cover
- spine
- complete dust jacket or full spread
- alternate angles or reference photographs

Queries should combine the detected title, author, ISBN, and localized terms such as `封面`, `背面`, `書脊`, `完整書衣`, `展開圖`, and equivalent English terms where useful.

### Candidate classification

Each candidate receives one proposed category:

- `front`
- `back`
- `spine`
- `full_spread`
- `reference_photo`
- `unknown`

Classification is heuristic and must remain editable by the user. Signals may include:

- query type that produced the result
- filename and surrounding title text
- source-page text supplied by the provider
- image aspect ratio and dimensions
- keywords such as `back`, `spine`, `dust jacket`, `wraparound`, `full cover`, `書脊`, `背面`, and `展開`

The system must not present the classification as certain when confidence is low.

### Candidate interface

Every candidate card displays:

- preview image
- proposed category
- title or source host
- provider
- known resolution
- source-page action
- rights information when supplied
- default warning: `授權狀態未確認；使用者需自行確認使用權`
- select action

The user can change the category before or after selecting the image.

### Download safety

Selected images must pass the shared validated-download path:

- HTTPS only
- bounded request timeout
- maximum download size of 50 MiB
- maximum decoded dimension of 20,000 × 20,000 pixels
- image MIME and actual image decoding validation
- temporary `.part` file followed by atomic replacement
- no credential-bearing URLs in cache metadata

### Credential behavior

Standard Windows mode stores credentials through the operating-system credential store when available.

Portable mode defaults to session-only credentials. Persisting credentials inside the portable data directory requires an explicit warning and second confirmation because the stored value may be readable by anyone with access to that folder.

If secure credential storage fails, the application must fall back to session-only behavior rather than silently storing plaintext.

### Applying selected images

The user can choose either composition mode at application time.

#### Segmented editing

- Front, back, and spine are independent regions.
- Each region can use a different image.
- Each image supports crop, scale, movement, replacement, and removal.
- Region edits remain undoable.

#### Composite full spread

- Front, back, and spine selections are composed into one flat spread.
- The user can adjust region boundaries and spine width before committing.
- The composed spread remains movable and croppable as one image.
- When the selected source is already a complete spread, it can be used directly without forced separation.

The application must not generate missing back or spine artwork. Missing regions remain blank or use user-created local elements.

---

## Module 2: EPUB Reflow as B6 Content on A5 Paper

### Purpose

Add a conversion mode that creates an editable Word document with:

- physical page size: A5, 148 × 210 mm
- centered content area: B6, 128 × 182 mm
- base horizontal margin: 10 mm on each side
- base vertical margin: 14 mm at top and bottom

This is semantic EPUB reflow, not page-image scaling and not cropping an existing A5 page.

### Reflow behavior

The converter must:

- rewrap text to the B6 content width
- repaginate based on B6 content height
- preserve editable text
- scale images proportionally to fit the B6 content area
- preserve chapter structure, headings, paragraphs, emphasis, and supported notes
- avoid cutting off text or images at the B6 boundary
- calculate page numbers, headers, and footers relative to the B6 content area

### Conversion interface

Add a layout choice to the existing converter:

- existing quarter-A4 mode
- `B6 內容置於 A5 紙張`

When the B6-on-A5 mode is selected, expose an output-mark choice:

- `普通列印`
- `附裁切標記`

`普通列印` is the default.

### Normal print output

- Word page remains A5.
- B6 content is centered.
- Outer area remains blank.
- No visible frame or crop marks are added.

### Crop-mark output

- Word page remains A5.
- B6 content remains centered and unchanged.
- Crop marks appear only outside the B6 content rectangle.
- Marks must not cross body text, images, headers, footers, or page numbers.
- Marks should be suitable for trimming the printed A5 sheet to 128 × 182 mm.

### Preview

The conversion page should show a simple preview of:

- A5 paper boundary
- centered B6 content boundary
- current mark mode

The preview is informational; the B6 content rectangle is fixed at 128 × 182 mm and is not draggable.

---

## Architecture

### Shared core

The shared Python package owns:

- normalized search request and candidate models
- Google Books and Open Library providers
- Google Custom Search provider
- merge, ranking, and deduplication
- candidate classification
- validated image download and cache
- B6-on-A5 geometry and crop-mark calculations
- conversion configuration serialization

### Windows desktop layer

The PySide6 desktop layer owns:

- asynchronous search workers
- credential dialogs and persistence selection
- candidate grid and category editing
- segmented/composite application dialogs
- conversion controls and preview
- progress, cancellation, and user-facing error messages

Network and conversion work must not block the UI thread.

### Data flow

1. Desktop reads document metadata and embedded images.
2. Desktop builds normalized search requests.
3. Shared providers return normalized candidates.
4. Shared classifier proposes candidate categories.
5. Desktop displays candidates and user corrections.
6. Shared downloader validates the selected original.
7. Desktop applies the image through an undoable cover-project mutation.
8. For B6 conversion, desktop passes the selected layout configuration to the shared converter and DOCX writer.

---

## Error Handling

Distinct Traditional Chinese messages are required for:

- no search results
- missing Google credentials
- invalid credentials
- quota exhaustion
- network timeout
- invalid or oversized image
- unsupported image format
- unavailable secure credential store
- unwritable portable data directory
- conversion failure

A partial search failure must still display candidates returned by other providers. A failed general-image search must not discard public-book or embedded candidates.

---

## Validation Strategy

Development should avoid repeatedly running the entire test matrix.

Required checks are limited to:

1. focused checks for new search/classification/download logic
2. focused checks for B6-on-A5 geometry and crop-mark placement
3. one desktop startup smoke check after UI integration
4. one final Windows portable build
5. manual user validation of real search results, image selection, cover composition, Word layout, and printed crop marks

The final build should be delivered for user testing before spending time on broad cross-platform verification.

---

## Acceptance Criteria

### Cover workflow

- Embedded covers appear immediately.
- Public-book search starts automatically from extracted metadata.
- Stored general-search credentials trigger automatic front/back/spine/full-spread searches.
- Missing credentials do not produce a blocking dialog.
- Results are classified but remain manually editable.
- No image is automatically applied.
- Segmented and composite modes are both available.
- No AI image generation occurs.

### B6-on-A5 conversion

- Output DOCX page size is A5.
- Editable EPUB content is reflowed inside a centered 128 × 182 mm rectangle.
- Normal and crop-mark modes are selectable.
- Normal mode shows no marks.
- Crop marks remain outside the content rectangle.
- Existing quarter-A4 behavior remains available and unchanged.
