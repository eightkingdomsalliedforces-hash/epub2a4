# Cover Editor Ghosting and Publisher Fonts Design

## Goal

Make the cover editor display one copy of each cover asset, repaint selection controls without trails, and reproduce the supplied publisher back-cover ISBN block as closely as possible without bundling proprietary font files.

## Confirmed visual reference

The supplied image is the back-cover ISBN and publisher-information block. It contains four distinct treatments:

1. `ISBN 978-986-237-077-3` in an OCR-B-style face.
2. EAN-13 human-readable digits in OCR-B.
3. Five-digit add-on digits above the supplemental barcode in OCR-B.
4. Rounded Traditional Chinese publisher text resembling DynaFont Yuan / 華康圓體, with a medium weight for the publisher name and a lighter weight for the remaining lines.

## Font policy

The repository must not bundle proprietary DynaFont files. The application will select installed fonts in this order:

- Publisher heading: `DFYuan-W5`, `華康圓體 Std W5`, `華康中圓體`, `Yuanti TC`, `PingFang TC`, `Microsoft JhengHei UI`, `Noto Sans CJK TC`, generic sans-serif.
- Publisher details: `DFYuan-W3`, `華康圓體 Std W3`, `華康細圓體`, `Yuanti TC`, `PingFang TC`, `Microsoft JhengHei UI`, `Noto Sans CJK TC`, generic sans-serif.
- ISBN and barcode digits: `OCR-B`, `OCR B Std`, `OCRB`, `OCR-B 10 BT`, `Liberation Mono`, `DejaVu Sans Mono`, generic monospace.

The desktop canvas uses Qt's installed-family database. The shared Pillow renderer searches explicit paths, environment overrides, and standard operating-system font directories using family/file hints. If a proprietary font is not installed, the application uses the documented fallback rather than silently scaling another font to imitate it.

## Font sizing

Project values remain typographic points. The Qt scene is expressed in millimetres, so canvas text converts points to scene millimetres using `pt × 25.4 / 72`. It must not pass the point number directly as a scene-sized font. Pillow export continues converting points using the selected export DPI.

The publisher block uses compact sizes and leading:

- ISBN label: 7 pt, OCR role.
- Publisher name: 7.5 pt, rounded medium role.
- Price, distributor/place, translator and other details: 6.5 pt, rounded regular role.
- Detail leading: 1.15.

The publisher name and detail lines are separate text elements so their weights and sizes are independent. Missing fields are omitted without moving the barcode.

## Barcode layout

The barcode remains programmatically drawn, not represented by a barcode font or generated image.

- EAN-13 main bars occupy the left portion.
- Guard bars extend lower than ordinary bars.
- The first EAN digit appears left of the main bars; the remaining two six-digit groups appear beneath their respective halves.
- A two- or five-digit add-on appears to the right when present.
- Add-on digits appear above the supplemental bars.
- Human-readable digits use the OCR font role.

The Qt editor and Pillow export use the same normalized measurements and module strings so their proportions agree.

## Cover replacement semantics

Applying a downloaded front, back or spine selection replaces existing image elements that occupy that same cover region. It does not append a second full-size cover image. Applying any panel selection also removes an existing full-spread image because it visually overlaps every panel. Applying a full-spread image replaces all existing front, back, spine and spread cover images.

Manually adding a decorative local image remains additive. The publisher-logo slot is therefore unaffected unless the user explicitly applies a back-cover replacement or deletes it.

## Selection-control repainting

Every graphics item's `boundingRect()` must contain all painted resize handles, the rotation line and the rotation handle. Content painting uses a separate unexpanded content rectangle. This lets Qt invalidate the complete old and new painted area during movement and removes blue control-handle trails.

## Existing preview-layer rule

The background raster editor preview continues excluding interactive image, text and barcode elements. Interactive content is drawn exactly once by Qt. PDF, DOCX and final preview rendering continue using the complete project.

## Testing

Regression tests cover:

- downloaded front cover replaces an existing source/front cover and does not leave two region images;
- full-spread replacement removes panel images;
- item bounding rectangles include selection controls while content rectangles retain the original element size;
- 24 pt converts to approximately 8.47 mm in the Qt scene;
- publisher template emits separate heading/details elements with the required font roles and compact sizes;
- OCR and rounded font candidate ordering;
- barcode normalized layout includes add-on digits above the supplement and EAN digit groups below the main bars;
- existing preview-layer exclusion remains green.

## Scope limits

- No font files or generated images are added.
- No online font download is performed.
- No schema-version increment is required; font-role and fallback lists remain ordinary element content fields.
- Existing projects using `font_family` continue to render.
