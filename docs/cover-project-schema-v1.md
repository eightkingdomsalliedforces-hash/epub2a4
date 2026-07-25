# CoverProject Schema v1

`CoverProject` is the canonical UTF-8 JSON contract shared by the Python core, Android JSON bridge, and future desktop clients. The physical coordinate system uses decimal millimetres, with the complete cover ordered **back | spine | front** from left to right.

## Root object

| Field | Type | Required | Rules |
|---|---|---:|---|
| `schema_version` | integer | yes | Must equal `1`. |
| `source_file` | string | yes | Original EPUB, DOCX, or PDF path. The service does not write beside it. |
| `source_type` | string | yes | `epub`, `docx`, or `pdf`. |
| `working_dir` | string | no | Writable service-owned work directory. Extracted or copied images are stored below `working_dir/assets`. |
| `metadata` | object | yes | Book metadata described below. |
| `trim_size` | object | yes | `width_mm` and `height_mm`; supported values are A5, A6, and 4×6 inch. |
| `page_count` | integer | yes | Confirmed or estimated body page count, greater than zero. |
| `paper_caliper_mm` | number | yes | Sheet thickness, greater than zero. |
| `manual_spine_width_mm` | number or null | yes | Positive manual override or `null`. |
| `bleed_mm` | number | yes | Range `0..10`. |
| `overlap_mm` | number | yes | Schema v1 requires exactly `5`. |
| `image_mode` | string | yes | `front_only` or `full_spread`. |
| `background` | object | no | JSON-safe background settings and warnings. |
| `elements` | array | no | Editable cover objects. IDs must be unique. |
| `export_settings` | object | no | DPI and print-mark booleans. |

Automatic spine width is `ceil(page_count / 2) × paper_caliper_mm`. A positive `manual_spine_width_mm` overrides it.

## Metadata

`metadata` supports `title`, `author`, `description`, `isbn`, `publisher`, `language`, `page_count_is_estimate`, and `embedded_images`. Text fields are strings. `embedded_images` is a JSON array of source inspection records.

## Elements

Each element contains:

- `id`: unique non-empty string.
- `kind`: `image`, `text`, `shape`, `barcode_placeholder`, or `guide`.
- `region`: `back`, `spine`, `front`, or `spread`.
- `transform`: `x_mm`, `y_mm`, positive `width_mm`, positive `height_mm`, and `rotation_deg`.
- `z_index`: integer; equal values retain source array order.
- `opacity`: number in `0..1`.
- `content`: kind-specific JSON object.

Image content requires a local existing `path`. Text content commonly includes `text`, `font_family`, `font_size_pt`, `color`, `align`, and `line_spacing`.

## Export settings

`export_settings.dpi` is a positive integer. PDF export accepts 200 or 300 DPI. `show_crop_marks` and `show_assembly_marks` are booleans. DOCX pages use exact A4 sections with zero margins; principal images and text remain editable OOXML objects.

## Compatibility

Readers must reject unknown schema versions and unknown fields. Writers must emit deterministic compact JSON through `dumps_project`. Paths are local filesystem paths and are never network URLs.
