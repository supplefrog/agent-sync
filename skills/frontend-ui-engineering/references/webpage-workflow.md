# Resource-Backed Webpage Workflow

Use this sequence for production pages and interfaces. Adapt its depth to the task; do not impose landing-page ceremony on a small product change.

## 1. Establish the brief

Capture the audience, job to be done, page type, primary action, real content, constraints, required states, and definition of success. Inspect the repository, running UI, existing design system, assets, routes, framework, and dependencies first.

If the user provides a screenshot, URL, video, gallery, component collection, or workflow, classify it before use:

- **Evidence of desired outcome:** match the relevant qualities closely.
- **Inspiration:** extract reusable principles, not pixels.
- **Code candidate:** inspect before importing.
- **Tool or service:** identify installation, network, account, cost, and data effects before invoking it.
- **Explanatory source:** decompose claims into reusable decisions, procedures, failure boundaries, checks, and canonical-source leads. Verify the durable parts, then remove the source itself from the live workflow.

Videos, talks, demos, and essays normally belong in the research record, not this skill's persistent references. Retain one only when future execution genuinely requires the exact artifact rather than the procedure extracted from it.

## 2. Set a coherent visual direction

Use `design-judgment.md` when it helps choose or revise a visual direction. Distinguish task, reading, decision and exploration surfaces. Capture only the decisions that distinguish this direction; inherited or irrelevant dimensions need no separate thesis. Use `taste-selection.md` for unresolved user taste before expensive implementation. Ordinary controls need no signature treatment.

When design choices are delegated, choose one considered result without requiring mockup comparisons or a taste questionnaire. Mix influences from reviewed skills, other sources, and original decisions as appropriate; coherence does not require a single design lineage. Select and tune the relevant taste dimensions using `design-judgment.md`, keeping unsupported values provisional. Current instructions and explicit approvals outrank inferred preferences; preserve an established identity even without a design document. A redesign may replace the authorized visual layer, not silently discard product facts, routes, behavior, or unrelated work.

Preserve an existing design system unless the user asks to change it. Create or expand a project `DESIGN.md` only when the user requests it or when the in-scope task establishes a multi-page or reusable design system. A bounded component or page change does not authorize a new project artifact. Prefer Google's current DESIGN.md structure: normative tokens plus human-readable rationale. Because the format is alpha, inspect the current specification before strict validation or automation.

A useful `DESIGN.md` records:

- product, audience, and visual thesis;
- colors, typography, spacing, radii, and layout rules;
- component and interaction patterns;
- imagery and icon direction;
- motion and reduced-motion behavior;
- accessibility constraints;
- explicit do and do-not examples.

## 3. Plan structure and assets

Resolve content order and responsive transformations before visual polish. Choose structure from the relationships between content, not a default hero-feature-CTA sequence. Reuse repeated layouts for genuinely comparable items and vary density when priority changes. Specify loading, empty, error, success, focus, hover, disabled, and overflow behavior where relevant.

Use real product facts. Clearly distinguish demonstration data from evidence; never fabricate commercial metrics, prices, endorsements, or capabilities to complete a proof section. When required facts are missing, request them or change the structure rather than disguising placeholders as truth.

Inventory existing assets first. Prefer authentic project assets over generic stock. If custom imagery, video, or frame sequences would materially improve the result, plan them after the layout direction is stable. Do not generate, purchase, upload, or fetch account-bound assets without authorization.

## 4. Implement from the inside out

Start with semantic structure, content, and core interactions. Reuse the project's components, tokens, icon library, and dependency choices. Add external code only when it solves a specific weakness that the current system does not.

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

## 5. Render, compare, and refine

Run the real page and inspect it in a browser. Batch relevant desktop and mobile captures, including the user's actual viewport when known, and exercise interaction states. Confirm captures show the right route and state with fonts and assets loaded; settle entrance motion before diagnosing invisible content as a defect. Compare against the brief and references by hierarchy, rhythm, typography, composition, behavior, and emotional tone rather than superficial resemblance.

Prioritize the observed bottleneck and functional/accessibility blockers. Use these areas as a diagnostic guide, not a fixed order:

1. content and information hierarchy;
2. layout and responsive behavior;
3. typography and spacing;
4. component states and accessibility;
5. imagery, icons, and motion;
6. decorative detail.

Replace only the weak sections. Distinguish observed defects from optional aesthetic alternatives. Batch material fixes and confirm the affected views; avoid full-page churn or indefinite polishing. Stop when the requested behavior and named quality checks hold, not when a self-score says the page is good. An unresolved functional or accessibility failure remains a blocker, not a taste preference.

## 6. Validate and deliver

Check the skill's verification list plus real content, slow or failed data, reduced motion, keyboard flow, console errors, image sizing, font loading, and performance at the target device class. Measure before claiming a performance improvement.

Use version-control checkpoints only inside an existing repository and without rewriting the user's work. Use Sites after the page is designed and implemented, and only for hosting or deployment.

## Workflow rationale

This workflow combines production engineering, subject-grounded visual direction, deliberate resource classification, targeted rendered refinement, and bounded delivery. These are retained as executable decisions rather than as dependencies on the explanatory material that surfaced them. Canonical references and their limits are recorded in `provenance.md`. The workflow deliberately excludes blanket tool installation, arbitrary framework mandates, copied designs, and animation as a default.
