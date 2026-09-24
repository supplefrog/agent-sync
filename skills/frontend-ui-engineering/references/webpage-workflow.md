# Resource and reference intake

Use when classifying supplied references, recovering or importing assets, importing components, or creating a requested/in-scope design-system document. Follow [SKILL.md](../SKILL.md) for the working sequence, design authority, and delivery checks; use [design-judgment.md](design-judgment.md), [taste-selection.md](taste-selection.md), and [motion-design.md](motion-design.md) when their decisions arise.

## Classify supplied sources

If the user provides a screenshot, URL, video, gallery, component collection, or workflow, classify it before use:

- **Evidence of desired outcome:** match the relevant qualities closely.
- **Inspiration:** extract reusable principles, not pixels.
- **Code candidate:** inspect before importing.
- **Tool or service:** identify installation, network, account, cost, and data effects before invoking it.
- **Explanatory source:** decompose claims into reusable decisions, procedures, failure boundaries, checks, and canonical-source leads. Verify the durable parts, then remove the source itself from the live workflow.

Videos, talks, demos, and essays normally belong in the research record, not this skill's persistent references. Retain one only when future execution genuinely requires the exact artifact rather than the procedure extracted from it.

## Design-system document boundary

Preserve an existing design system unless the user asks to change it. Create or expand a project `DESIGN.md` only when requested or when the in-scope task establishes a multi-page or reusable design system. A bounded component or page change does not authorize a new project artifact. Prefer Google's current DESIGN.md structure: normative tokens plus human-readable rationale. Because the format is alpha, inspect the current specification before strict validation or automation.

A useful `DESIGN.md` records:

- product, audience, and visual thesis;
- colors, typography, spacing, radii, and layout rules;
- component and interaction patterns;
- imagery and icon direction;
- motion and reduced-motion behavior;
- accessibility constraints;
- explicit do and do-not examples.

## Inventory assets and components

Inventory existing assets first. Prefer authentic project assets over generic stock. If custom imagery, video, or frame sequences would materially improve the result, plan them after the layout direction is stable. Do not generate, purchase, upload, or fetch account-bound assets without authorization.

### Recover an insufficient image

- Keep an existing image that suits the intended rendered size/device pixel ratio and required framing. Otherwise check supplied files, project originals, and the source page's download link, `srcset`, or media metadata before substituting it.
- For a public image, try URL-based reverse search or descriptive/exact-caption search, then follow a matching result to its source page and largest suitable asset. Switch to descriptive search if reverse search is blocked or irrelevant. Keep private/local-only images and signed URLs within local or explicitly authorized sources.
- Default budget: one reverse-search service, three keyword queries, and three promising source pages; stop at a verified suitable match. Use the host's blocked-page recovery workflow within this budget (`web-source-access` where available). If exhausted, report the gap and ask for the original or agreement on a smaller display or alternative.
- Download and decode candidates; record source-page and asset URLs, actual dimensions, and visual comparison of subject, detail, and required framing. HTTP success or size labels alone do not verify a match. A host's “original” means its upload variant, not proven camera-original provenance; check reuse rights before importing.
- Preserve the full source when available. Requested crops or upscaling are derivatives, not recovered detail; label them accordingly.

### Import components

Add external code only when it solves a specific weakness that the current system does not.

For each imported component, verify:

- source and license;
- framework and version compatibility;
- transitive dependencies and bundle cost;
- keyboard and screen-reader behavior;
- reduced-motion fallback;
- responsive and content-overflow behavior;
- visual adaptation to project tokens;
- removal or rollback path.

Animation should explain change, preserve context, or reinforce the visual thesis. Do not make GSAP, parallax, or scroll-driven spectacle a default. For cinematic pages, treat frame sequences and synchronized scroll as a specialized recipe and verify load cost and reduced-motion behavior.

## Capture validity

Before diagnosing a render, confirm the capture shows the correct route and state with fonts and assets loaded; let entrance motion settle before treating invisible content as a defect.
