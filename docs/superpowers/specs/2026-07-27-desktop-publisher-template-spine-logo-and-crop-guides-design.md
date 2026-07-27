# Desktop publisher template, spine preset, logo search, and crop guides design

Date: 2026-07-27
Branch: `fix/reference-back-cover-isbn-clarity`

## 1. Scope

This specification adds four related desktop capabilities:

1. A shared publisher metadata editor which is available both before creating a cover project and inside the cover editor.
2. A combined publisher back-cover and vertical spine template based on the supplied reference layout.
3. Publisher logo search with a user-selected candidate list, local caching, and project embedding.
4. A single, predictable desktop crop/fold guide control which drives preview and DOCX output from the same shared geometry.

No image is generated, redrawn, or stylistically transformed. Publisher logos are either downloaded from identified sources or selected manually by the user.

## 2. Goals

- Desktop users can enter and later edit every publisher-template field without recreating the project.
- Applying the combined template creates both the publisher back-cover block and the vertical spine layout.
- Changing metadata updates template-managed content while preserving user-adjusted positions, sizes, rotation, opacity, and z-order.
- Publisher selection can search multiple public sources and present candidates for explicit user selection.
- Downloaded logos remain usable offline because the selected file is cached and copied into the cover project.
- Desktop preview and exported DOCX use one `PagePlacement` and `CropGuide` result.
- B6-on-A5 displays two full cutting lines at `x=20 mm` and `y=28 mm` when crop guides are enabled.

## 3. Non-goals

- Do not generate publisher logos or approximate them with AI.
- Do not automatically choose a logo candidate without user confirmation.
- Do not redistribute commercial font files.
- Do not require network access to reopen or export an existing project.
- Do not reset manually adjusted template geometry during ordinary metadata edits.
- Do not add unrelated Android UI changes in this desktop specification.

## 4. Shared publisher metadata panel

### 4.1 Architecture

Create one reusable desktop widget, provisionally named `PublisherMetadataPanel`. Both the cover setup page and the cover editor use this same component. Validation, normalization, labels, and serialization are implemented once.

### 4.2 Fields

The panel exposes:

- ISBN-13 or convertible ISBN-10
- ISBN add-on
- Publisher
- Price
- Publication place or distributor/agent information
- Translator
- English title or subtitle
- Volume or issue number
- Volume/arc/chapter label
- Series name
- Internal book code
- Spine accent colour
- Publisher logo asset

The existing title and author remain sourced from normal cover metadata and do not need duplicate input fields in this panel.

### 4.3 Validation

- ISBN may be blank.
- A non-blank ISBN must pass ISBN-10 or ISBN-13 validation and is stored canonically as ISBN-13.
- ISBN add-on may be blank, exactly two digits, or exactly five digits.
- Text fields are trimmed but preserve internal punctuation and spacing.
- Accent colour must be a valid UI colour value; invalid values do not replace the last valid value.
- Logo selection is optional.

Validation errors are shown next to the relevant field. Invalid values are not committed to the project.

### 4.4 Setup-page behaviour

- Source metadata fills fields when available.
- Users may override extracted metadata before creating the project.
- Selecting the publisher template does not require every field to be present.
- The complete metadata override is included in the `new_project` settings boundary.

### 4.5 Editor behaviour

- The same panel is available in the editor side panel.
- Changes are debounced for approximately 300 ms before updating the project and preview.
- Updating metadata only regenerates template-managed content.
- User-created elements are untouched.
- Metadata remains stored when another template is active and becomes visible again when the publisher template is reapplied.

## 5. Combined publisher back-cover and spine template

### 5.1 Template identity

Introduce or rename the template to a clear combined identity such as:

`publisher_back_matter_with_spine`

The UI label is:

`出版社封底＋直式書脊`

The existing publisher back-cover-only identifier remains readable for backward compatibility and may map to the combined implementation when the project includes a spine region.

### 5.2 Back-cover block

The back-cover layout continues to provide:

- ISBN label
- EAN-13 barcode
- optional two- or five-digit add-on barcode
- publisher name
- price
- publication place/distributor/agent line
- translator line

Rules:

- Publisher name and detail lines share the same left edge.
- Missing lines are removed and following lines move upward.
- The block shrinks to actual content height; no fixed empty area remains below it.
- Publisher name uses the publisher-heading font role.
- Detail lines use the publisher-detail font role.
- ISBN text uses the OCR font role.
- Exact `DFPYuanW5-GB` and `DFPYuanW3-GB` names remain first-choice candidates when installed.

### 5.3 Spine layout

The spine uses a white base and vertically arranged content inspired by the supplied reference:

- publisher or series logo at the top
- main Chinese title in the central area
- optional English title/subtitle beside or below the main title
- prominent volume/issue number
- optional arc/chapter label
- author in the lower half
- internal book code and publisher name at the bottom

Each item is a template-managed element with a stable element ID. The logical spine group can be moved, scaled, rotated, hidden, deleted, and restored as one undoable operation while individual elements may still be selected for advanced adjustment.

### 5.4 Spine-width breakpoints

The template selects one of three deterministic layouts from the calculated spine width:

- `>= 10 mm`: full layout, including logo, Chinese title, English subtitle, volume, arc/chapter, author, internal code, and publisher name.
- `>= 6 mm and < 10 mm`: compact layout, smaller type and reduced secondary information.
- `< 6 mm`: minimal layout with Chinese title, volume/issue number, and publisher name only.

When the spine is too narrow for the minimal layout at the configured print size, the editor shows a warning but does not block export.

### 5.5 Metadata updates without geometry reset

When metadata changes:

- Existing template-managed elements retain their current transform, opacity, z-order, and grouping.
- Text and image content are replaced in place.
- Elements which become empty are hidden or removed according to the template rule.
- Newly needed elements are inserted at their default location relative to the current group anchor.
- Only the explicit `重設模板版面` action restores all template geometry to defaults.

## 6. Publisher directory and selection

### 6.1 Publisher directory

Maintain a lightweight local publisher catalogue containing:

- stable publisher ID
- display name
- aliases
- official website domains
- official social links when known
- default logo search terms
- default publisher-name typography and spacing parameters
- optional default spine layout parameters

A publisher not present in the directory remains fully supported through a custom text entry.

### 6.2 Changing publisher

When the publisher value changes, the editor asks whether to:

- update only the publisher text; or
- also search for a replacement logo and apply publisher-specific defaults.

A manually selected logo is never silently overwritten.

## 7. Logo search and candidate selection

### 7.1 Sources

Search may use:

1. official publisher websites
2. official social accounts
3. Wikimedia Commons
4. Wikipedia
5. other publicly accessible image sources

Only HTTP and HTTPS sources are accepted.

### 7.2 Candidate list

Search results are presented in a candidate dialog. No result is selected automatically.

Each candidate shows:

- thumbnail
- publisher or logo title
- source domain
- source category: official, official social, Wikimedia, Wikipedia, or other
- official-source badge when verified
- dimensions
- file format
- transparent-background status when detectable
- licence or usage information when available
- explicit `授權資訊未知` when no reliable licence data is available

The first page displays no more than approximately 20 candidates.

### 7.3 Ranking

Candidates are ranked by:

1. verified official source
2. official social source
3. transparent background
4. SVG, then high-resolution PNG
5. publisher-name match quality
6. adequate resolution

Small images, photographs, screenshots, duplicate results, and weak name matches are demoted.

### 7.4 Selection workflow

- Selecting a candidate opens a larger preview with source and licence details.
- Confirming the candidate downloads and validates the file.
- The logo is inserted at the spine top and any configured back-cover logo slot.
- Rendering uses `contain`; the logo is never cropped to fill the slot.
- The original aspect ratio is preserved.
- Users may choose `重新搜尋`, `修改關鍵字`, `手動選擇圖片`, or `不使用 Logo`.

### 7.5 Download security

- Enforce timeouts, redirect limits, and a maximum download size.
- Validate the actual file signature and decoded dimensions.
- Reject unsupported or corrupt content.
- SVG is parsed safely; scripts, external resource loads, and active content are prohibited.
- A failed download leaves the existing project and logo unchanged.

### 7.6 Cache and project embedding

The selected logo stores:

- project asset ID
- local cache path
- original source URL
- source category
- download timestamp
- image format and dimensions
- licence text or status
- official-source flag
- manual-selection flag

The selected bytes are copied into the project asset store. Export reads the project copy and never requires network access.

## 8. Desktop crop and fold guide control

### 8.1 One user-facing control

Desktop output uses one checkbox:

`顯示裁切／折線`

There is no separate hidden B6 mark-mode control. Changing the checkbox or output mode immediately recomputes the preview.

### 8.2 Shared geometry

The desktop preview and DOCX writer consume the same `PagePlacement` and `CropGuide` values from the shared Python core. The UI must not independently recalculate guide coordinates.

### 8.3 Mode rules

#### B6 on A5

- A5 paper: `148 × 210 mm`
- B6 content: `128 × 182 mm`
- B6 content rectangle: `x=20, y=28, width=128, height=182 mm`
- Full horizontal crop line: `(0,28) -> (148,28)`
- Full vertical crop line: `(20,0) -> (20,210)`
- Both are solid crop lines.

#### A4 four-up

- one full internal vertical solid crop line
- one full internal horizontal solid crop line
- shared edges are emitted once

#### 16-page signature

- fold positions use dashed fold lines
- actual cut positions use solid crop lines
- crop and fold roles remain distinct in the data model and renderer

#### Single A5 and single 4×6

When the paper is the finished size, no internal guides are emitted. The UI displays `紙張邊緣即成品邊`.

### 8.4 Preview and export parity

- Turning guides off removes them from both preview and DOCX.
- Changing mode updates both from the same result.
- Guide line width defaults to `0.35 pt`.
- The generated DOCX is inspected to confirm expected guide coordinates.
- LibreOffice PDF rendering is used as a visual regression check.

### 8.5 Compatibility mode

Some readers may not render VML lines consistently. Add an optional advanced output mode:

`高相容裁切線`

This uses a page-content or border-based representation rather than header VML. The default remains the existing header-layer method where it is known to work. The compatibility mode must preserve the same coordinates and line roles.

## 9. Persistence and backward compatibility

Extend project metadata with optional fields for:

- publisher ID
- English title/subtitle
- volume/issue number
- arc/chapter label
- series name
- internal book code
- spine accent colour
- selected logo metadata

All new fields have empty or null defaults. Existing schema-v1 projects load without migration failure. Existing projects with the older publisher template remain editable.

## 10. Error handling

- Metadata validation errors are field-specific and do not discard other edits.
- Search failures show a recoverable message and retain the previous candidate list when appropriate.
- Download failures never remove the current logo.
- Missing cached files fall back to the embedded project asset.
- Missing embedded assets show a clear warning and allow reselection.
- A template update that cannot preserve an element transform aborts without replacing the current project.
- Network features are optional; offline cover editing and export remain available.

## 11. Testing

### 11.1 Metadata and UI

- setup and editor use the same field definitions
- setup values cross the service boundary correctly
- editor changes persist after project save and reopen
- ISBN and add-on validation
- old schema-v1 project loading

### 11.2 Template layout

- missing back-cover fields compact upward
- no fixed empty area remains below publisher details
- three spine-width breakpoints
- metadata updates preserve transforms
- explicit reset restores defaults
- spine group undo/redo behaviour

### 11.3 Logo search

- source-category labelling
- official-source verification
- ranking and duplicate suppression
- download size and timeout handling
- file-signature validation
- safe SVG rejection tests
- cache reuse and offline reopen
- manual logo is not overwritten
- project embedding survives source removal

### 11.4 Crop guides

- desktop UI forwards the checkbox state
- B6 full-line coordinates
- four-up crop lines
- signature crop/fold roles
- guide-off behaviour
- DOCX XML inspection
- LibreOffice render verification
- high-compatibility guide path

### 11.5 Platform regression

Run shared Python tests and desktop PySide6 tests on Windows, macOS, and Linux. Build the Windows portable package. Android builds remain a shared-core compatibility check but receive no new product UI from this specification.

## 12. Implementation order

1. Extract the shared publisher metadata panel and wire it into setup and editor.
2. Extend optional project metadata and persistence.
3. Implement metadata-preserving publisher back-cover updates.
4. Add the three-breakpoint vertical spine template and combined template ID.
5. Add publisher directory, logo candidate models, search adapters, candidate dialog, secure downloader, cache, and project embedding.
6. Unify desktop crop/fold controls with shared geometry and add preview parity.
7. Add the optional high-compatibility guide renderer.
8. Run full shared, desktop, render, and packaging verification.

## 13. Acceptance criteria

The work is accepted when:

- all publisher and spine fields can be entered before project creation and edited later;
- the combined template creates a compact back-cover block and adaptive vertical spine;
- users explicitly choose among logo candidates and the selected logo works offline;
- metadata edits do not reset manual template geometry;
- desktop preview and DOCX show the same crop/fold guides;
- B6-on-A5 shows two full cutting lines at `x=20 mm` and `y=28 mm` when enabled;
- all specified tests and platform checks pass;
- no generated images or bundled commercial fonts are introduced.
