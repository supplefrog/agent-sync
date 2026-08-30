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

Write a one-sentence visual thesis grounded in the product's subject and audience. Decide the hierarchy, typography role, palette role, density, geometry, image treatment, and motion character. Take one meaningful aesthetic risk only when it supports the product.

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

Resolve content order and responsive transformations before visual polish. Specify loading, empty, error, success, focus, hover, disabled, and overflow behavior where relevant.

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

Run the real page and inspect it in a browser. Capture relevant desktop and mobile widths and exercise interaction states. Compare against the brief and references by hierarchy, rhythm, typography, composition, behavior, and emotional tone rather than superficial resemblance.

Refine in this order:

1. content and information hierarchy;
2. layout and responsive behavior;
3. typography and spacing;
4. component states and accessibility;
5. imagery, icons, and motion;
6. decorative detail.

Replace only the weak sections. Avoid full-page churn when a targeted component change will close the gap.

## 6. Validate and deliver

Check the skill's verification list plus real content, slow or failed data, reduced motion, keyboard flow, console errors, image sizing, font loading, and performance at the target device class. Measure before claiming a performance improvement.

Use version-control checkpoints only inside an existing repository and without rewriting the user's work. Use Sites after the page is designed and implemented, and only for hosting or deployment.

## Workflow rationale

This workflow combines production engineering, subject-grounded visual direction, deliberate resource classification, targeted rendered refinement, and bounded delivery. These are retained as executable decisions rather than as dependencies on the explanatory material that surfaced them. Canonical references and their limits are recorded in `provenance.md`. The workflow deliberately excludes blanket tool installation, arbitrary framework mandates, copied designs, and animation as a default.
