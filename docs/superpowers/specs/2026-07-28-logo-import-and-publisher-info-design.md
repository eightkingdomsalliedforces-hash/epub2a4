# Logo Import and Publisher Information Design

## Problems

The v0.6.2 Windows Desktop build passes an `svg_converter` keyword argument
to both `download_logo()` and `import_logo_file()`, but neither shared API
accepts that argument. Manual Logo selection therefore raises a `TypeError`,
and Logo search has the same latent failure.

Publisher metadata updates correctly store the translator, but template
refresh preserves the old publisher-detail rectangle. When translator text or
wrapping adds lines, the rectangle remains too short and clips the new content.
The current 7.5 pt heading and 6.5 pt detail sizes are also too small.

## Logo Import Design

Both shared Logo entry points accept an optional callable:

```python
SvgConverter = Callable[[bytes, int, int], bytes]
```

SVG input is first validated by the existing active-content checks. When a
converter is supplied, the validated SVG bytes and dimensions are passed to
the converter, the returned PNG is validated as a raster image, and the stored
`DownloadedLogo` describes the PNG output. Without a converter, shared and
Android callers retain the existing SVG-preserving behavior.

Raster formats do not invoke the converter. Desktop continues supplying its Qt
SVG rasterizer from both manual import and online Logo search.

## Publisher Information Design

The publisher heading starts at 10 pt. Price, publication or agency
information, and translator start at 9 pt. Existing wrapping remains enabled;
font reduction remains available only when a line cannot fit the fixed width.

During metadata-only template refresh, the publisher heading and details retain
their user-adjusted X/Y positions and widths. Their heights expand to at least
the newly generated layout height. If the heading grows taller, the details
rectangle moves down by the same growth so the two blocks do not overlap.
Other template-managed elements retain the existing geometry-preservation
behavior.

This allows a newly entered translator to become visible without resetting the
whole template or discarding manual horizontal placement.

## Data Flow

1. Desktop input emits `PublisherMetadataValues`.
2. The controller updates `CoverMetadata.translator`.
3. `refresh_template_metadata()` regenerates publisher text content at 10/9 pt.
4. The merge step expands the old publisher rectangles where required.
5. Canvas, PDF, and DOCX render the same updated project elements.

## Tests and Acceptance Criteria

- Manual PNG import succeeds while accepting the optional converter argument
  without calling it.
- Manual SVG import and online SVG download invoke the converter and store a
  validated PNG.
- A controller-level manual Logo test reproduces and prevents the reported
  `unexpected keyword argument 'svg_converter'` failure.
- Adding a translator to an existing publisher template produces visible
  translator content and a taller details rectangle.
- The publisher heading is 10 pt and detail text is 9 pt when it fits.
- Heading growth moves details down rather than overlapping it.
- Existing metadata, Logo safety, rendering, Desktop, Android, and packaging
  tests pass.

## Release

After local and GitHub CI verification, merge the repair and publish v0.6.3
using the existing tag-triggered Release workflow.
