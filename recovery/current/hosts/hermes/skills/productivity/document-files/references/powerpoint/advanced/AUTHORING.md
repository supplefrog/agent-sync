# Advanced PowerPoint authoring with PptxGenJS

**Active authoring route; visual verification deferred.** The two known
image-size parser advisories are removed from this dependency graph: the
local PptxGenJS repack removes its unused image-size dependency without
changing any authoring code. This is a local manifest-only adaptation, not
an upstream security release. Provenance and unchanged-file hashes are in
`vendor/provenance.json`; `npm audit` and the regression tests verify the
installed graph. Reassess this removal on every PptxGenJS upgrade.

Use this route when the Python helpers are too constrained for precise text runs, spacing, effects, SVG, or styled merged tables. It is an additive route, not a replacement for the Python create/read/edit helpers.

## Reproducible setup

This directory pins a manifest-only repack of `pptxgenjs` 4.0.1 through a local
tarball in `package.json` and `package-lock.json`. Use this package when
authoring rather than fetching the unmodified vulnerable dependency graph.
From this directory (select Python with python-pptx, Pillow, defusedxml and
PyMuPDF available):

```bash
npm ci --ignore-scripts
npm audit --omit=dev
npm run test:security
npm run build:probe
npm run verify:probe
```

`build:probe` writes `output/advanced-authoring-probe.pptx`; `verify:probe` reopens the OOXML package with Python and checks the required structures.

The Python checks use existing python-pptx, Pillow, defusedxml, and PyMuPDF.
The build repairs a PptxGenJS Node interoperability defect: its SVG fallback
can contain SVG bytes labeled as PNG. `normalize_svg_fallbacks.py` makes a
real PNG fallback while preserving the native SVG part. Run it only on the
freshly authored trusted deck. Its temporary ZIP is deleted after replacement
or failure; it does not leave rollback copies. All raster parts are decoded
in verification, rather than treating filenames or ZIP entries as proof.

## Authoring patterns

- **Rich text and character spacing:** pass an array of `{ text, options }` runs to `slide.addText`; use run-level `bold`, `italic`, `color`, `fontFace`, and `charSpacing`.
- **Margins and bullets:** text-box `margin` is in points and accepts a scalar or TRBL array. Apply `bullet` to each run/paragraph and use `indentLevel` for hierarchy. Keep body text left-aligned.
- **Shapes and shadows:** use `pptx.ShapeType` plus `fill`, `line`, and `shadow`. Shadows require explicit type/color/angle/blur/offset/opacity; subtle outer shadows are safer than heavy effects.
- **Images and SVG:** `addImage` accepts a local/remote `path` or pre-encoded `data`. Pre-encoded data is deterministic and avoids runtime fetching. Standard raster formats are broadly compatible. Native SVG display requires newer desktop PowerPoint or Microsoft 365; for mixed/older viewers, rasterize an SVG to PNG before authoring or supply a separately tested fallback asset.
- **Merged styled tables:** cell objects accept `colspan`/`rowspan` plus cell-level fill, borders, margins, alignment, and rich-text arrays. Always set table width/column widths when using `colspan`, and inspect the resulting grid structure.
- **Layout:** set `pptx.layout = "LAYOUT_WIDE"` for 16:9. Use at least 0.5 inch edge clearance, 0.3–0.5 inch gaps, a clear title/body type scale, and explicit x/y/w/h. Treat automatic table paging and text fit as estimates that still need visual review.

## Verification boundary

Structural read-back proves the deck opens as OOXML and contains the expected text runs, spacing, bullets, shadows, image parts, SVG relationships, and table merge markup. It does **not** prove that text fits, elements do not overlap, fonts resolve, or SVG renders in a particular viewer. Renderer selection and dependency installation are deferred until real presentation work starts, not visual QA itself. At that point choose a suitable renderer (not necessarily LibreOffice), render every slide, inspect it and fix defects before final delivery. Without that verification, the output is a draft. Do not infer better visual quality from the richer authoring API or structural test results. A clean dependency audit is not a blanket guarantee that arbitrary media are safe; inspect external assets and avoid unbounded downloads.

## Sources

New guidance and example code were authored from the MIT PptxGenJS library and its official documentation:

- Text: https://gitbrent.github.io/PptxGenJS/docs/api-text.html
- Shapes: https://gitbrent.github.io/PptxGenJS/docs/api-shapes.html
- Images: https://gitbrent.github.io/PptxGenJS/docs/api-images
- Tables: https://gitbrent.github.io/PptxGenJS/docs/api-tables.html
- Saving: https://gitbrent.github.io/PptxGenJS/docs/usage-saving.html
