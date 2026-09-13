---
name: document-files
description: Use for office documents, PDFs, sheets, and OCR.
---
# Document files

Load every branch matching an input or output format.

## Routing
- Word `.docx`: `references/docx/SKILL.md`
- PDF creation/editing/security: `references/pdf/SKILL.md`
- PDF/scanned-document OCR: `references/pdf/SKILL.md` and `references/pdf/references/ocr-extraction.md`
- Optional natural-language PDF page editing: `references/pdf/SKILL.md` and `references/pdf/references/nano-pdf-editing.md`
- Excel `.xlsx` and CSV: `references/xlsx/SKILL.md`
- PowerPoint `.pptx`: `references/powerpoint/SKILL.md`

## Shared workflow
1. Inventory files, formats, page/sheet/slide counts, and requested mutations.
2. Preserve originals unless in-place editing is explicit.
3. Inspect before editing; never infer contents from filenames.
4. Use native helpers and preserve structure, styles, formulas, links, and metadata.
5. Write to an explicit output path.
6. Re-open or parse the artifact and run format-specific validation; render representative views when possible. When preview-before-download is requested, inspect the actual compiled/exported PDF or page images rendered from it, and deliver that same PDF; an HTML approximation does not validate pagination, font embedding, or clipping.
7. Report paths and verification limits.

## Resume and LaTeX revision workflow

1. Preserve each source bundle separately, including `.cls`, `.sty`, fonts, and assets. Check existing project support before adding another editor or scoring service; compilation support and automatic content-extraction support are different capabilities. Preserve the user's template options rather than redesigning solely to satisfy a narrow parser.
2. Compile historical baselines in separate working directories before changing the template. With Tectonic available, run `tectonic --untrusted --keep-logs Resume_SDE.tex` from each copied bundle's directory; verify source hashes afterward and inspect the actual rendered pages plus extracted text. Label these as historical reproductions, not approved resumes. A blocked hosted scorer need not stall independent local compilation and parser checks.
3. Establish the factual baseline before optimizing wording. Treat an earlier AI-written resume as a draft, not ground truth; apply explicit user corrections to the project's canonical profile so rejected claims cannot return through source-file reuse. Keep employment, completed personal projects, and proposed projects distinct.
4. Choose a real JD for matching, or label the review as general resume quality. Prefer a focused professional narrative over a larger inventory of disconnected technologies.
5. Compare like with like: hold content fixed when testing layouts, and layout fixed when testing wording. Record the scorer, exact PDF identity, JD or no-JD status, observed score, visible feedback, and free-tier limits. Do not name an empirical winner until the same inputs have actually been tested.
6. Keep PDF parseability, factual support, JD coverage, and writing quality separate. A source-HTML structural score does not test the compiled LaTeX PDF; proprietary checker percentages are not interchangeable employer-ATS pass probabilities. Never raise a score by inventing skills, metrics, or employment scope.

Each guide remains a complete nested package under `references/<format>/`, retaining internal scripts and links.